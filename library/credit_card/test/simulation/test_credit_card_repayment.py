# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
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
    create_outbound_authorisation_instruction,
    create_outbound_hard_settlement_instruction,
    create_settlement_event,
    create_transfer_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase

CONTRACT_FILE = "library/credit_card/contracts/template/credit_card.py"
ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"
CONTRACT_FILES = [CONTRACT_FILE, ASSET_CONTRACT_FILE, LIABILITY_CONTRACT_FILE]
DEFAULT_DENOM = "GBP"
EXPIRE_INTEREST_FREE_PERIODS_WORKFLOW = "CREDIT_CARD_EXPIRE_INTEREST_FREE_PERIODS"
PUBLISH_STATEMENT_DATA_NOTIFICATION = "PUBLISH_STATEMENT_DATA_NOTIFICATION"

default_instance_params = DEFAULT_CREDIT_CARD_INSTANCE_PARAMS
default_template_params = DEFAULT_CREDIT_CARD_TEMPLATE_PARAMS


class CreditCardRepaymentTest(SimulationTestCase):
    """
    Test handling of payment due date and repayment
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
        :param scod_workflow: dict[str, Any], the workflow object from the simulation results
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

    def test_no_interest_acc_from_scod_is_charged_if_balance_paid_off_in_full_before_pdd(
        self,
    ):
        """
        - Spend and accrue from day after SCOD
        - repay before the due date
        - cancel interest charge for positive balance
        - next scod - no interest billed
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {**default_instance_params}
        template_params = {
            **default_template_params,
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 11, 5, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="SCOD 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("100")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("1100")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay and check accrual",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1100",
                        event_datetime=datetime(2019, 2, 5, 9, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 5, 9, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("2.64"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="PDD - no interest charged",
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("REVOLVER"), Decimal("0")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
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
            SubTest(
                description="SCOD - no interest billed",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                            (BalanceDimensions("REVOLVER"), Decimal("0")),
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

    def test_no_interest_acc_from_txn_is_charged_if_balance_paid_off_in_full_before_pdd(
        self,
    ):
        """
        - Spend and accrue from day after SCOD
        - repay before the due date
        - cancel interest charge for positive balance
        - next scod - no interest billed
        """
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {**default_instance_params}
        template_params = {**default_template_params}

        sub_tests = [
            SubTest(
                description="Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 11, 5, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="SCOD 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("100")),
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("1100")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1100")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay and check accrual",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1100",
                        event_datetime=datetime(2019, 2, 5, 9, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 5, 9, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("16.50"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="PDD - no interest charged",
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("REVOLVER"), Decimal("0")),
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
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD - no interest billed",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
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
                                Decimal("0"),
                            ),
                            (BalanceDimensions("REVOLVER"), Decimal("0")),
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

    def test_full_repayment_when_revolver_int_acc_from_scod(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 28, 3, tzinfo=ZoneInfo("UTC"))

        instance_params = {**default_instance_params}
        template_params = {
            **default_template_params,
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Spend 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("OVERDUE_1"), Decimal("200")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("2000")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (BalanceDimensions("ANNUAL_FEES_UNPAID"), Decimal("100")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (BalanceDimensions("REVOLVER"), Decimal("-1")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("33"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("2200")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2233"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial Repay after PDD",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="400",
                        event_datetime=datetime(2019, 2, 27, 8, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 27, 8, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("OVERDUE_1"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1700")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (BalanceDimensions("ANNUAL_FEES_UNPAID"), Decimal("0")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (BalanceDimensions("REVOLVER"), Decimal("-1")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("34.32"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1800")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1834.32"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial Repay after PDD 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1800",
                        event_datetime=datetime(2019, 2, 28, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 28, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("35.44"),
                            ),
                            (BalanceDimensions("REVOLVER"), Decimal("-1")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("35.44"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("35.44"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial Repay after PDD 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="35.44",
                        event_datetime=datetime(2019, 2, 28, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 28, 3, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("REVOLVER"), Decimal("0")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("0")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
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

    def test_full_repayment_when_revolver_int_acc_from_txn(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 28, 3, tzinfo=ZoneInfo("UTC"))

        instance_params = {**default_instance_params}
        template_params = {**default_template_params}

        sub_tests = [
            SubTest(
                description="Spend 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000", event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("OVERDUE_1"), Decimal("200")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("2000")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (BalanceDimensions("ANNUAL_FEES_UNPAID"), Decimal("100")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (BalanceDimensions("REVOLVER"), Decimal("-1")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("73.92"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("2200")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2273.92"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial Repay after PDD",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="400",
                        event_datetime=datetime(2019, 2, 27, 8, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 27, 8, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("OVERDUE_1"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1700")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (BalanceDimensions("ANNUAL_FEES_UNPAID"), Decimal("0")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (BalanceDimensions("REVOLVER"), Decimal("-1")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("75.24"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1800")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1875.24"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial Repay after PDD 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1800",
                        event_datetime=datetime(2019, 2, 28, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 28, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("76.36"),
                            ),
                            (BalanceDimensions("REVOLVER"), Decimal("-1")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("76.36"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("76.36"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial Repay after PDD 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="76.36",
                        event_datetime=datetime(2019, 2, 28, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 28, 3, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("REVOLVER"), Decimal("0")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("0")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
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

    def test_pdd_schedule_is_not_affected_by_weekends(self):
        """
        Use the SCOD workflow to assert PDD dates
        """

        start = datetime(year=2019, month=1, day=24, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=7, day=10, hour=1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "payment_due_period": "21",
        }
        template_params = {**default_template_params}

        date_1 = datetime(year=2019, month=2, day=24, tzinfo=ZoneInfo("UTC")) + relativedelta(
            seconds=2
        )
        date_2 = datetime(year=2019, month=3, day=27, tzinfo=ZoneInfo("UTC")) + relativedelta(
            seconds=2
        )
        date_3 = datetime(year=2019, month=4, day=26, tzinfo=ZoneInfo("UTC")) + relativedelta(
            seconds=2
        )
        date_4 = datetime(year=2019, month=5, day=27, tzinfo=ZoneInfo("UTC")) + relativedelta(
            seconds=2
        )
        date_5 = datetime(year=2019, month=6, day=26, tzinfo=ZoneInfo("UTC")) + relativedelta(
            seconds=2
        )

        sub_tests = [
            SubTest(
                description="Check number of SCOD workflows triggered is correct",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
                        timestamp=date_1,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={
                            "account_id": "Main account",
                            "current_payment_due_date": "2019-03-16",
                            "minimum_amount_due": "100.00",
                            "start_of_statement_period": "2019-01-24",
                            "end_of_statement_period": "2019-02-23",
                            "current_statement_balance": "100.00",
                            "next_payment_due_date": "2019-04-16",
                            "next_statement_cut_off": "2019-03-26",
                            "is_final": "False",
                        },
                    ),
                    ExpectedContractNotification(
                        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
                        timestamp=date_2,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={
                            "account_id": "Main account",
                            "current_payment_due_date": "2019-04-16",
                            "minimum_amount_due": "200.00",
                            "start_of_statement_period": "2019-02-24",
                            "end_of_statement_period": "2019-03-26",
                            "current_statement_balance": "200.00",
                            "next_payment_due_date": "2019-05-16",
                            "next_statement_cut_off": "2019-04-25",
                            "is_final": "False",
                        },
                    ),
                    ExpectedContractNotification(
                        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
                        timestamp=date_3,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={
                            "account_id": "Main account",
                            "current_payment_due_date": "2019-05-16",
                            "minimum_amount_due": "300.00",
                            "start_of_statement_period": "2019-03-27",
                            "end_of_statement_period": "2019-04-25",
                            "current_statement_balance": "300.00",
                            "next_payment_due_date": "2019-06-16",
                            "next_statement_cut_off": "2019-05-26",
                            "is_final": "False",
                        },
                    ),
                    ExpectedContractNotification(
                        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
                        timestamp=date_4,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={
                            "account_id": "Main account",
                            "current_payment_due_date": "2019-06-16",
                            "minimum_amount_due": "400.00",
                            "start_of_statement_period": "2019-04-26",
                            "end_of_statement_period": "2019-05-26",
                            "current_statement_balance": "400.00",
                            "next_payment_due_date": "2019-07-16",
                            "next_statement_cut_off": "2019-06-25",
                            "is_final": "False",
                        },
                    ),
                    ExpectedContractNotification(
                        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
                        timestamp=date_5,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={
                            "account_id": "Main account",
                            "current_payment_due_date": "2019-07-16",
                            "minimum_amount_due": "500.00",
                            "start_of_statement_period": "2019-05-27",
                            "end_of_statement_period": "2019-06-25",
                            "current_statement_balance": "500.00",
                            "next_payment_due_date": "2019-08-16",
                            "next_statement_cut_off": "2019-07-26",
                            "is_final": "False",
                        },
                    ),
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

    def test_all_pdds_on_last_day_of_month_if_first_pdd_is_on_last_day_of_month(self):
        """
        Use the SCOD workflow to assert PDD dates
        """

        start = datetime(year=2019, month=2, day=10, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=7, day=10, hour=1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "payment_due_period": "22",
        }
        template_params = {**default_template_params}

        date_1 = datetime(year=2019, month=3, day=10, tzinfo=ZoneInfo("UTC")) + relativedelta(
            seconds=2
        )
        date_2 = datetime(year=2019, month=4, day=9, tzinfo=ZoneInfo("UTC")) + relativedelta(
            seconds=2
        )
        date_3 = datetime(year=2019, month=5, day=10, tzinfo=ZoneInfo("UTC")) + relativedelta(
            seconds=2
        )
        date_4 = datetime(year=2019, month=6, day=9, tzinfo=ZoneInfo("UTC")) + relativedelta(
            seconds=2
        )
        date_5 = datetime(year=2019, month=7, day=10, tzinfo=ZoneInfo("UTC")) + relativedelta(
            seconds=2
        )

        sub_tests = [
            SubTest(
                description="Check number of SCOD workflows triggered is correct",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
                        timestamp=date_1,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={
                            "account_id": "Main account",
                            "current_payment_due_date": "2019-03-31",
                            "minimum_amount_due": "100.00",
                            "start_of_statement_period": "2019-02-10",
                            "end_of_statement_period": "2019-03-09",
                            "current_statement_balance": "100.00",
                            "next_payment_due_date": "2019-04-30",
                            "next_statement_cut_off": "2019-04-08",
                            "is_final": "False",
                        },
                    ),
                    ExpectedContractNotification(
                        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
                        timestamp=date_2,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={
                            "account_id": "Main account",
                            "current_payment_due_date": "2019-04-30",
                            "minimum_amount_due": "200.00",
                            "start_of_statement_period": "2019-03-10",
                            "end_of_statement_period": "2019-04-08",
                            "current_statement_balance": "200.00",
                            "next_payment_due_date": "2019-05-31",
                            "next_statement_cut_off": "2019-05-09",
                            "is_final": "False",
                        },
                    ),
                    ExpectedContractNotification(
                        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
                        timestamp=date_3,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={
                            "account_id": "Main account",
                            "current_payment_due_date": "2019-05-31",
                            "minimum_amount_due": "300.00",
                            "start_of_statement_period": "2019-04-09",
                            "end_of_statement_period": "2019-05-09",
                            "current_statement_balance": "300.00",
                            "next_payment_due_date": "2019-06-30",
                            "next_statement_cut_off": "2019-06-08",
                            "is_final": "False",
                        },
                    ),
                    ExpectedContractNotification(
                        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
                        timestamp=date_4,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={
                            "account_id": "Main account",
                            "current_payment_due_date": "2019-06-30",
                            "minimum_amount_due": "400.00",
                            "start_of_statement_period": "2019-05-10",
                            "end_of_statement_period": "2019-06-08",
                            "current_statement_balance": "400.00",
                            "next_payment_due_date": "2019-07-31",
                            "next_statement_cut_off": "2019-07-09",
                            "is_final": "False",
                        },
                    ),
                    ExpectedContractNotification(
                        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
                        timestamp=date_5,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={
                            "account_id": "Main account",
                            "current_payment_due_date": "2019-07-31",
                            "minimum_amount_due": "500.00",
                            "start_of_statement_period": "2019-06-09",
                            "end_of_statement_period": "2019-07-09",
                            "current_statement_balance": "500.00",
                            "next_payment_due_date": "2019-08-31",
                            "next_statement_cut_off": "2019-08-09",
                            "is_final": "False",
                        },
                    ),
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

    @skip("UTC offset not in scope for conversion")
    def test_next_pdd_not_affected_if_local_and_utc_month_different(self):
        # The combination of start date and payment due period means the PDD
        # falls on the 1st of the month, which in UTC is the 16:00 on last day
        # of the previous month

        start = datetime(year=2019, month=1, day=8, tzinfo=ZoneInfo("UTC"))
        end = datetime(year=2019, month=4, day=10, second=2, tzinfo=ZoneInfo("UTC"))

        instance_params = {**default_instance_params, "payment_due_period": "22"}
        template_params = {**default_template_params}

        date_1 = start + relativedelta(months=1, seconds=2)
        date_2 = start + relativedelta(months=2, seconds=2)
        date_3 = start + relativedelta(months=3, seconds=2)

        sub_tests = [
            SubTest(
                description="Check number of SCOD workflows triggered is correct",
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
                        timestamp=date_1,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={
                            "account_id": "Main account",
                            "current_payment_due_date": "2019-03-01",
                            "minimum_amount_due": "100.00",
                            "start_of_statement_period": "2019-01-08",
                            "end_of_statement_period": "2019-02-07",
                            "current_statement_balance": "100.00",
                            "next_payment_due_date": "2019-04-01",
                            "next_statement_cut_off": "2019-03-10",
                            "is_final": "False",
                        },
                    ),
                    ExpectedContractNotification(
                        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
                        timestamp=date_2,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={
                            "account_id": "Main account",
                            "current_payment_due_date": "2019-04-01",
                            "minimum_amount_due": "200.00",
                            "start_of_statement_period": "2019-02-08",
                            "end_of_statement_period": "2019-03-10",
                            "current_statement_balance": "200.00",
                            "next_payment_due_date": "2019-05-01",
                            "next_statement_cut_off": "2019-04-09",
                            "is_final": "False",
                        },
                    ),
                    ExpectedContractNotification(
                        notification_type=PUBLISH_STATEMENT_DATA_NOTIFICATION,
                        timestamp=date_3,
                        resource_id="Main account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                        notification_details={
                            "account_id": "Main account",
                            "current_payment_due_date": "2019-05-01",
                            "minimum_amount_due": "300.00",
                            "start_of_statement_period": "2019-03-11",
                            "end_of_statement_period": "2019-04-09",
                            "current_statement_balance": "300.00",
                            "next_payment_due_date": "2019-06-01",
                            "next_statement_cut_off": "2019-05-10",
                            "is_final": "False",
                        },
                    ),
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

    def test_overdue_and_unpaid_rebalanced_correctly_for_fix_mad(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 26, 12, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
        }
        template_params = {
            **default_template_params,
            "minimum_amount_due": "200",
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Spend 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000", event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1100")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("100")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("900")),
                        ]
                    }
                },
            ),
            SubTest(
                description="PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1216.5")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("1000")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("200")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("16.5"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_UNPAID"), Decimal("100")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial Repay after PDD",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 2, 26, 8, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 8, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("716.5")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("600")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("16.5"),
                            ),
                            (BalanceDimensions("ANNUAL_FEES_UNPAID"), Decimal("0")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Full Repay after PDD",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="716.5",
                        event_datetime=datetime(2019, 2, 26, 12, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 12, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
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

    def test_no_overdue_for_partial_repayment_above_fixed_mad_before_pdd(self):
        """
        Spend 1000 GBP
        Make sure MAD balance is based on fixed amount parameter (200GBP)
        Make sure UNPAID/OVERDUE balances rebalanced correctly at PDD
        Pay back 1100 GBP after PDD
        Verify repayment is distributed
        """

        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 26, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {**default_instance_params}
        template_params = {
            **default_template_params,
            "minimum_amount_due": "200",
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Spend 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1100")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("100")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay above MAD on time",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500", event_datetime=datetime(2019, 2, 1, 2, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("600")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("0")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("9.75"),
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

    def test_over_settle(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {**default_instance_params, "credit_limit": "10000", "annual_fee": "0"}
        template_params = {**default_template_params}

        sub_tests = [
            SubTest(
                description="Initial Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="500",
                        client_transaction_id="A",
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9500")),
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
                        amount="700",
                        final=True,
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="A",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("9300")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("700")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("700"),
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

    def test_deposit_balance_populated_when_overpaying_and_spent_from_first(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {**default_instance_params, "credit_limit": "30000", "annual_fee": "800"}
        template_params = {**default_template_params}

        sub_tests = [
            SubTest(
                description="Initial spend",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29000")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1000")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1000"),
                            ),
                            (BalanceDimensions("DEPOSIT"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Over repay to create deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("31000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("-1000"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("-1000"),
                            ),
                            (BalanceDimensions("DEPOSIT"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Spend from deposit (1)",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="300",
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("30700")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("-700")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("-700"),
                            ),
                            (BalanceDimensions("DEPOSIT"), Decimal("700")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Spend from deposit (2)",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="200", event_datetime=datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 4, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("30500")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("-500")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("-500"),
                            ),
                            (BalanceDimensions("DEPOSIT"), Decimal("500")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Fee taken from deposit and credit",
                expected_balances_at_ts={
                    datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29700")),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("300")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("300"),
                            ),
                            (BalanceDimensions("DEPOSIT"), Decimal("0")),
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

    def test_deposit_balance_accounts_for_charged_interest_when_overpaying(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 24, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }
        template_params = {**default_template_params, "accrue_interest_from_txn_day": "False"}

        sub_tests = [
            SubTest(
                description="Initial spend",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10000",
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("10000"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("10000"),
                            ),
                            (BalanceDimensions("DEPOSIT"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check PDD charges interest",
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("10000"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("10144.76"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("144.76"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Over-pay after pdd to create deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="11000",
                        event_datetime=datetime(2019, 2, 23, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("30855.24"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("-855.24"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("-855.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("DEPOSIT"), Decimal("855.24")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Spend from deposit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 2, 24, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("30355.24"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("-355.24"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("-355.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("DEPOSIT"), Decimal("355.24")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Spend from deposit and credit line",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 2, 24, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("29355.24"),
                            ),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("644.76"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("644.76"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNCHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("DEPOSIT"), Decimal("0")),
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

    def test_deposit_balance_unaffected_by_auth_and_used_when_over_settling_auth(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "late_repayment_fee": "0",
            "annual_fee": "0",
        }
        template_params = {**default_template_params}

        sub_tests = [
            SubTest(
                description="Initial Auth",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="A",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
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
                            (BalanceDimensions("DEPOSIT"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Over payment",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="15000",
                        event_datetime=datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 2, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("35000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("-15000"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("-15000"),
                            ),
                            (BalanceDimensions("DEPOSIT"), Decimal("15000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Over settle",
                events=[
                    create_settlement_event(
                        amount="11000",
                        final=True,
                        event_datetime=datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC")),
                        client_transaction_id="A",
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 3, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("34000")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("-4000"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("-4000"),
                            ),
                            (BalanceDimensions("DEPOSIT"), Decimal("4000")),
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

    def test_repayment_hierarchy_no_late_fees(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 0, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "overlimit": "3000",
            "overlimit_fee": "0",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    }
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
                    "cash_advance": "0",
                    "balance_transfer": "0",
                    "transfer": "0",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
            "minimum_amount_due": "200",
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        client_transaction_id="1",
                        event_datetime=datetime(2019, 1, 10, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="5000",
                        client_transaction_id="1",
                        final=True,
                        event_datetime=datetime(2019, 1, 10, second=1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="3000",
                        client_transaction_id="2",
                        event_datetime=datetime(2019, 1, 15, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="3000",
                        client_transaction_id="2",
                        final=True,
                        event_datetime=datetime(2019, 1, 15, second=1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Purchase 3",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="2000",
                        client_transaction_id="3",
                        event_datetime=datetime(2019, 1, 20, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="2000",
                        client_transaction_id="3",
                        final=True,
                        event_datetime=datetime(2019, 1, 20, second=1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Check SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("MAD_BALANCE"),
                                Decimal("200"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 4",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="3500",
                        client_transaction_id="4",
                        event_datetime=datetime(2019, 2, 10, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="3500",
                        client_transaction_id="4",
                        final=True,
                        event_datetime=datetime(2019, 2, 10, second=1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Repayment 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="50", event_datetime=datetime(2019, 2, 22, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="Check After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 23, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("174.62"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("9950")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("3500")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("MAD_BALANCE"),
                                Decimal("512.16"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 5",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="5",
                        event_datetime=datetime(2019, 3, 10, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="1000",
                        client_transaction_id="5",
                        final=True,
                        event_datetime=datetime(2019, 3, 10, second=1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Repayment 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="80", event_datetime=datetime(2019, 3, 22, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="Check After PDD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 23, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("203.06"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("147.66"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("13450")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check SCOD 3",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("MAD_BALANCE"), Decimal("1012.88")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("362.16")),
                            (BalanceDimensions("OVERDUE_2"), Decimal("70")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("288.56"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("147.66"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("13450")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
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

    def test_repayment_hierarchy_late_repayment_overdue_charges(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 0, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "overlimit": "3000",
            "overlimit_fee": "0",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    }
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "6000"}}),
            "late_repayment_fee": "200",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
            "minimum_percentage_due": dumps(
                {
                    "purchase": "0.01",
                    "cash_advance": "0",
                    "balance_transfer": "0",
                    "transfer": "0",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
            "minimum_amount_due": "200",
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="5000",
                        client_transaction_id="1",
                        event_datetime=datetime(2019, 1, 10, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="5000",
                        client_transaction_id="1",
                        final=True,
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="3000",
                        client_transaction_id="2",
                        event_datetime=datetime(2019, 1, 15, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="3000",
                        client_transaction_id="2",
                        final=True,
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Purchase 3",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="2000",
                        client_transaction_id="3",
                        event_datetime=datetime(2019, 1, 20, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="2000",
                        client_transaction_id="3",
                        final=True,
                        event_datetime=datetime(2019, 1, 20, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Check SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("MAD_BALANCE"),
                                Decimal("200"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 4",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="3500",
                        client_transaction_id="4",
                        event_datetime=datetime(2019, 2, 10, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="3500",
                        client_transaction_id="4",
                        final=True,
                        event_datetime=datetime(2019, 2, 10, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Repayment 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="50", event_datetime=datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="Check After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("201.26"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("9950")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("3500")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("MAD_BALANCE"),
                                Decimal("712.28"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase 5",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="5",
                        event_datetime=datetime(2019, 3, 10, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="1000",
                        client_transaction_id="5",
                        final=True,
                        event_datetime=datetime(2019, 3, 10, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Repayment 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="80", event_datetime=datetime(2019, 3, 25, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="Check After PDD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 26, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("231.56"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("147.78"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("13450")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_UNPAID"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("562.28")),
                            (BalanceDimensions("OVERDUE_2"), Decimal("70")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check SCOD 3",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("MAD_BALANCE"), Decimal("1613.12")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("562.28")),
                            (BalanceDimensions("OVERDUE_2"), Decimal("70")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("288.56"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("147.78"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("13450")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_UNPAID"),
                                Decimal("200"),
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

    def test_repayment_hierarchy_repay_under_mad_late_fees_billed(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "overlimit": "3000",
            "overlimit_fee": "0",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    }
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "6000"}}),
            "late_repayment_fee": "200",
            "annual_fee": "0",
        }
        template_params = {
            **default_template_params,
            "minimum_percentage_due": dumps(
                {
                    "purchase": "0.01",
                    "cash_advance": "0",
                    "balance_transfer": "0",
                    "transfer": "0",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
            "minimum_amount_due": "200",
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="32000",
                        client_transaction_id="1",
                        event_datetime=datetime(2019, 1, 10, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="32000",
                        client_transaction_id="1",
                        final=True,
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Check SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("MAD_BALANCE"),
                                Decimal("2320"),
                            )
                        ]
                    }
                },
            ),
            SubTest(
                description="Check before Repayment 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("483.92"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("32000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repayment 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1500",
                        event_datetime=datetime(2019, 2, 24, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Check After Repayment 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 25, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("503.97"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("30500")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repayment 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="80", event_datetime=datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="Check After Repayment 2",
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("523.97"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("30420")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("MAD_BALANCE"), Decimal("1828.17")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("740")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("583.97"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("200"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("30420")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repayment 3",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 3, 30, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Check After Repayment 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 31, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("600"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("83.97"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("30420")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_UNPAID"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("200"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("1088.17")),
                            (BalanceDimensions("OVERDUE_2"), Decimal("240")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check SCOD 3",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("MAD_BALANCE"), Decimal("2736.34")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("620"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("83.97"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("30420")),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_UNPAID"),
                                Decimal("200"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_BILLED"),
                                Decimal("200"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("1088.17")),
                            (BalanceDimensions("OVERDUE_2"), Decimal("240")),
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

    def test_repayment_hier_ca_int_billed_and_purchase_int_billed_and_chrgd(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "40000",
            "payment_due_period": "21",
            "overlimit": "0",
            "overlimit_fee": "0",
            "transaction_type_fees": dumps(
                {
                    "cash_advance": {
                        "over_deposit_only": "False",
                        "percentage_fee": "0.02",
                        "flat_fee": "100",
                    }
                }
            ),
            "transaction_type_limits": dumps({"cash_advance": {"flat": "7000"}}),
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
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="15000",
                        client_transaction_id="1",
                        event_datetime=datetime(2019, 1, 10, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="15000",
                        client_transaction_id="1",
                        final=True,
                        event_datetime=datetime(2019, 1, 10, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Cash Advance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="7000",
                        event_datetime=datetime(2019, 1, 15, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                        client_transaction_id="a",
                    )
                ],
            ),
            SubTest(
                description="Purchase 2",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="2",
                        event_datetime=datetime(2019, 1, 20, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="10000",
                        client_transaction_id="2",
                        final=True,
                        event_datetime=datetime(2019, 1, 20, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Check SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("MAD_BALANCE"), Decimal("577.3")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("140"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("25000")),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("7000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("117.3"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check After PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 24, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("25000")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("7000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("117.3"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("140"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("378.12"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("158.70"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repayment 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="300",
                        event_datetime=datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Check After Repayment 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("25000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("6957.3"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("411.00"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("172.46"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("MAD_BALANCE"), Decimal("1250.23")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("277.3")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("6957.3"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("25000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("460.32"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("193.04"),
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

    def test_repayment_hierarchy_ca_repayment_purchase_interest_billed_and_charged(
        self,
    ):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 0, 1, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "credit_limit": "30000",
            "payment_due_period": "21",
            "overlimit": "3000",
            "overlimit_fee": "0",
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
                description="Cash Advance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="15000",
                        event_datetime=datetime(2019, 1, 10, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                        client_transaction_id="a",
                    )
                ],
            ),
            SubTest(
                description="Check SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("MAD_BALANCE"), Decimal("775.38")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("300"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_BILLED"),
                                Decimal("15000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("325.38"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repayment 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 2, 22, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Purchase 1",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="17000",
                        client_transaction_id="1",
                        event_datetime=datetime(2019, 2, 25, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                    create_settlement_event(
                        amount="17000",
                        client_transaction_id="1",
                        final=True,
                        event_datetime=datetime(2019, 2, 25, 2, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="Check SCOD 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("MAD_BALANCE"), Decimal("3304.22")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("675.38")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("300"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("15000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("225.38"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("414.12"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("44.72"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("17000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repayment 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 3, 22, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="Check After Repayment 2",
                expected_balances_at_ts={
                    datetime(2019, 3, 23, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("17000")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("2304.22")),
                            (BalanceDimensions("OVERDUE_2"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("14984.22"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("17000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("245.96"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("325.37"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Check SCOD 3",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("MAD_BALANCE"), Decimal("3429.03")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("17000")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("2304.22")),
                            (BalanceDimensions("OVERDUE_2"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_UNPAID"),
                                Decimal("14984.22"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("17000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("346.58"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("458.39"),
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

    # TODO: needed or duplicated?
    def test_pdd_considers_partial_repayment_after_cutoff(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 23, 0, 0, 1, tzinfo=ZoneInfo("UTC"))

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
                    }
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
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Pre-SCOD 1 Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 30, 0, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 30, 0, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 0, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("1000")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1000"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial Repay during PDD 1 schedule lag",
                # PDD runs at 1 secs past
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 2, 23, 0, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("900")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("14.52"),
                            ),
                            (BalanceDimensions("REVOLVER"), Decimal("-1")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("100")),
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

    def test_pdd_considers_partial_repayment_after_cutoff_int_acc_from_txn(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 23, 0, 0, 1, tzinfo=ZoneInfo("UTC"))

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
                    }
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
                description="Pre-SCOD 1 Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 30, 0, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 30, 0, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 0, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("1000")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1000"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial Repay during PDD 1 schedule lag",
                # PDD runs at 1 secs past
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100",
                        event_datetime=datetime(2019, 2, 23, 0, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("900")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("15.84"),
                            ),
                            (BalanceDimensions("REVOLVER"), Decimal("-1")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("100")),
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

    def test_pdd_considers_full_repayment_after_cutoff(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 23, 0, 0, 1, tzinfo=ZoneInfo("UTC"))

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
                    }
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
                description="Pre-SCOD 1 Purchase",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 30, 0, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 30, 0, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 0, 0, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("STATEMENT_BALANCE"), Decimal("1000")),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("1000"),
                            ),
                            (BalanceDimensions("OUTSTANDING_BALANCE"), Decimal("1000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("200")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Over Repay during PDD 1 schedule lag",
                # PDD runs at 1 secs past
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=datetime(2019, 2, 23, 0, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
            ),
            SubTest(
                description="PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 23, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        # No interest is charged as we consider live balances, instead of cut-off
                        "Main account": [
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("OVERDUE_1"), Decimal("0")),
                            (BalanceDimensions("DEPOSIT"), Decimal("1000")),
                        ]
                    }
                },
            )
            # We can't test postings coming in after the effective date but before the schedule
            # runs as simulator assumes 0 delay between logical schedule and actual execution
            # time
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_repayment_hierarchy_ca_unpaid_interest_purchase_unpaid_interest_acc_from_scod(
        self,
    ):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC"))

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
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {**default_template_params, "accrue_interest_from_txn_day": "False"}

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="123456",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("10000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="10000",
                        client_transaction_id="123456",
                        final=True,
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16120")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("13880")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("6000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances A",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16220.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13779.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("10000")),
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
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("6000")),
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
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances B",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16570.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13429.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
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
                                Decimal("184.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
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
                                Decimal("165.76"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("1111.28")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("17670.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("12329.36"),
                            ),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("165.76"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay A",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="270", event_datetime=datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("17818.52")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("12181.48"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
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
                                Decimal("203.98"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("180.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("213.90"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
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

    def test_repayment_hierarchy_ca_unpaid_interest_purchase_unpaid_interest_acc_from_txn(
        self,
    ):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC"))

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
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {**default_template_params}

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="123456",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("10000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="10000",
                        client_transaction_id="123456",
                        final=True,
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16120")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("13880")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("6000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances A",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16220.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13779.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("10000")),
                            (
                                BalanceDimensions(self.PURCHASE_INT_PRE_SCOD_UNCHRGD),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions(self.PURCHASE_INT_POST_SCOD_UNCHRGD),
                                Decimal("203.98"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("6000")),
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
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances B",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16774.62")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13225.38"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
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
                                Decimal("388.22"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
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
                                Decimal("165.76"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("1315.26")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("17874.62")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("12125.38"),
                            ),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("165.76"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay A",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="270", event_datetime=datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("18022.50")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("11977.50"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
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
                                Decimal("203.98"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("384.62"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("213.90"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
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

    def test_repayment_hierarchy_fees_unpaid_fees_statement(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC"))

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
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {**default_template_params, "accrue_interest_from_txn_day": "False"}

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="123456",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("10000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="10000",
                        client_transaction_id="123456",
                        final=True,
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16120")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("13880")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("6000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances A",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16220.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13779.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("10000")),
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
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("6000")),
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
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances B",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16570.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13429.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
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
                                Decimal("184.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
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
                                Decimal("165.76"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("1111.28")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("17670.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("12329.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("184.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances C",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 0, 5, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("18088.52")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("11911.48"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("203.98"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("184.24"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("213.90"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("266.40"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
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
                description="Repay A",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="968.52",
                        event_datetime=datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("17120")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("12880")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("20"),
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

    def test_repayment_hierarchy_ca_unpaid_ca_statement(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC"))

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
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {**default_template_params, "accrue_interest_from_txn_day": "False"}

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="123456",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("10000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="10000",
                        client_transaction_id="123456",
                        final=True,
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16120")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("13880")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("6000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances A",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16220.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13779.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("10000")),
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
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("6000")),
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
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances B",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16570.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13429.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
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
                                Decimal("184.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
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
                                Decimal("165.76"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("1111.28")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("17670.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("12329.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("184.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances C",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 0, 5, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("18088.52")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("11911.48"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("203.98"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("184.24"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("213.90"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("266.40"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay A",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2088.52",
                        event_datetime=datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("14000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("5000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
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

    def test_repayment_hierarchy_purchase_unpaid_purchase_statement(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC"))

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
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {**default_template_params, "accrue_interest_from_txn_day": "False"}

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="123456",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("10000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="10000",
                        client_transaction_id="123456",
                        final=True,
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16120")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("13880")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("6000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances A",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16220.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13779.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("10000")),
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
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("6000")),
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
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances B",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16570.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13429.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
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
                                Decimal("184.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
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
                                Decimal("165.76"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("1111.28")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Auth B",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="1000",
                        client_transaction_id="234567",
                        event_datetime=datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16570.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("12429.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("1000")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("184.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement B",
                events=[
                    create_settlement_event(
                        amount="1000",
                        client_transaction_id="234567",
                        final=True,
                        event_datetime=datetime(2019, 3, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("17570.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("12429.36"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("1000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("184.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances C",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 0, 5, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("17978.29")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("12021.71"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("224.13"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("184.24"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("183.52"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("266.40"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay A",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="7978.29",
                        event_datetime=datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("9000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
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

    def test_repayment_hierarchy_int_unpaid_by_apr_int_statement_by_apr(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC"))

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
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {**default_template_params, "accrue_interest_from_txn_day": "False"}

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="123456",
                        event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("10000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="10000",
                        client_transaction_id="123456",
                        final=True,
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16120")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("13880")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("6000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances A",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16220.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13779.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("10000")),
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
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("6000")),
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
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances B",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16570.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13429.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
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
                                Decimal("184.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
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
                                Decimal("165.76"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("1111.28")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("17670.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("12329.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("184.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("165.76"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances C",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 0, 5, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("18088.52")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("11911.48"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("203.98"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("184.24"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("213.90"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("266.40"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay A",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="800", event_datetime=datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("17288.52")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("12711.48"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("68.52"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("1000")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
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

    def test_repayment_hierarchy_ca_int_charged_purchase_int_charged(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 4, 11, 1, tzinfo=ZoneInfo("UTC"))

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
            "transaction_type_limits": dumps({"cash_advance": {"flat": "8000"}}),
            "late_repayment_fee": "0",
            "annual_fee": "0",
            "overlimit_opt_in": "True",
            "overlimit_fee": "180",
        }
        template_params = {**default_template_params, "accrue_interest_from_txn_day": "False"}

        sub_tests = [
            SubTest(
                description="Purchase Auth A",
                events=[
                    create_outbound_authorisation_instruction(
                        amount="10000",
                        client_transaction_id="123456",
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("10000")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Purchase Settlement A",
                events=[
                    create_settlement_event(
                        amount="10000",
                        client_transaction_id="123456",
                        final=True,
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("10000")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("20000")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal A",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="6000",
                        event_datetime=datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 15, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16120")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("13880")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("10000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("6000"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("120"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances A",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16220.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13779.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("10000")),
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
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("6000")),
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
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances B",
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("16570.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("13429.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
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
                                Decimal("184.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("0")),
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
                                Decimal("165.76"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("1111.28")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Cash Withdrawal B",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 3, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("17670.64")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("12329.36"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_AUTH"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("184.24"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1000"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("165.76"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("100.64"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                            (BalanceDimensions("OVERDUE_1"), Decimal("380.64")),
                        ]
                    }
                },
            ),
            SubTest(
                description="Statement Balances C",
                expected_balances_at_ts={
                    datetime(2019, 4, 1, 0, 5, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("18088.52")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("11911.48"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("203.98"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("184.24"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("213.90"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("266.40"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Pre-Repay Balances",
                expected_balances_at_ts={
                    datetime(2019, 4, 11, 0, 5, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("18223.32")),
                            (
                                BalanceDimensions("AVAILABLE_BALANCE"),
                                Decimal("11911.48"),
                            ),
                            (BalanceDimensions("PURCHASE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("10000")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("65.80"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("203.98"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("184.24"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("6000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("69"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("213.90"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_UNPAID"),
                                Decimal("266.40"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
                                Decimal("120"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repay A",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="18157.52",
                        event_datetime=datetime(2019, 4, 11, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 4, 11, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("65.80")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("30000")),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("0")),
                            (BalanceDimensions("PURCHASE_UNPAID"), Decimal("0")),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_CHARGED"),
                                Decimal("65.80"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("PURCHASE_INTEREST_UNPAID"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_UNPAID"), Decimal("0")),
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
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_UNPAID"),
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

    def test_txn_level_repayment_hierarchy(self):
        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 1, 31, 7, 0, 0, 1, tzinfo=ZoneInfo("UTC"))

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
            "transaction_types": default_template_update(
                "transaction_types",
                {
                    "balance_transfer": {"charge_interest_from_transaction_date": "True"},
                    "cash_advance": {"charge_interest_from_transaction_date": "True"},
                },
            ),
            "base_interest_rates": default_template_update(
                "base_interest_rates", {"cash_advance": "0.36"}
            ),
            "annual_percentage_rate": default_template_update(
                "annual_percentage_rate", {"cash_advance": "2"}
            ),
            "minimum_percentage_due": dumps(
                {
                    "purchase": "0.2",
                    "cash_advance": "0.2",
                    "transfer": "0.2",
                    "balance_transfer": "0.2",
                    "interest": "1.0",
                    "fees": "1.0",
                }
            ),
        }

        sub_tests = [
            SubTest(
                description="Balance Transfer REF1",
                events=[
                    create_transfer_instruction(
                        amount="1000",
                        debtor_target_account_id="Main account",
                        creditor_target_account_id="Dummy account",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF1",
                        },
                        event_datetime=datetime(2019, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
                    ),
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
                    create_transfer_instruction(
                        amount="5000",
                        debtor_target_account_id="Main account",
                        creditor_target_account_id="Dummy account",
                        instruction_details={
                            "transaction_code": "bb",
                            "transaction_ref": "REF2",
                        },
                        event_datetime=datetime(2019, 1, 1, 2, tzinfo=ZoneInfo("UTC")),
                    ),
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
                        event_datetime=datetime(2019, 1, 1, 3, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
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
                description="Check Interest",
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("8292.30")),
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
                                Decimal("18"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("115.20"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("59.10"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="10", event_datetime=datetime(2019, 1, 31, 2, tzinfo=ZoneInfo("UTC"))
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("8282.30")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("21910")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("4990"),
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
                                Decimal("18"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("115.20"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("59.10"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="5000",
                        event_datetime=datetime(2019, 1, 31, 3, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 3, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("3282.30")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("26910")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("1000"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_CHARGED"),
                                Decimal("1990"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("18"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("115.20"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("59.10"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment 3",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="2000",
                        event_datetime=datetime(2019, 1, 31, 4, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 4, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("1282.30")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("28910")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("990"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("18"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("115.20"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("59.10"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment 4",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 31, 5, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 5, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("282.30")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29900")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("18"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("105.20"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("59.10"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment 5",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="115.20",
                        event_datetime=datetime(2019, 1, 31, 6, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 6, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("167.10")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29900")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("18"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_INTEREST_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_CHARGED"),
                                Decimal("49.10"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Partial repayment 6",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="59.10",
                        event_datetime=datetime(2019, 1, 31, 7, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 7, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("108")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("29900")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
                                Decimal("100"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_INTEREST_CHARGED"),
                                Decimal("8"),
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
                description="Repayment 7",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="108",
                        event_datetime=datetime(2019, 1, 31, 7, 0, 0, 1, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 1, 31, 7, 0, 0, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("DEFAULT"), Decimal("0")),
                            (BalanceDimensions("AVAILABLE_BALANCE"), Decimal("30000")),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF1_CHARGED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("BALANCE_TRANSFER_REF2_CHARGED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("CASH_ADVANCE_CHARGED"), Decimal("0")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_CHARGED"),
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

    def test_payment_allowed_during_repayment_holiday(self):
        """
        Verify that when in a repayment holiday (i.e. MAD will be calculated to be 0),
        we can still make repayments, and see the repaid sum distributed according to the
        repayment hierarchy.
        """

        start = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        end = datetime(2019, 2, 26, 2, tzinfo=ZoneInfo("UTC"))

        instance_params = {
            **default_instance_params,
            "transaction_type_limits": dumps({}),
            "credit_limit": "5000",
        }
        template_params = {
            **default_template_params,
            "mad_equal_to_zero_flags": dumps(["REPAYMENT_HOLIDAY"]),
            "overdue_amount_blocking_flags": dumps(["REPAYMENT_HOLIDAY"]),
            "billed_to_unpaid_transfer_blocking_flags": dumps(["REPAYMENT_HOLIDAY"]),
            "accrue_interest_from_txn_day": "False",
        }

        sub_tests = [
            SubTest(
                description="Spend 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2000", event_datetime=datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
                    )
                ],
            ),
            SubTest(
                description="Cash advance 1",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1000",
                        event_datetime=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                        instruction_details={"transaction_code": "aaa"},
                    )
                ],
            ),
            SubTest(
                description="Bank issues repayment holiday",
                events=[
                    create_flag_definition_event(
                        timestamp=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                    ),
                    create_flag_event(
                        timestamp=datetime(2019, 1, 2, tzinfo=ZoneInfo("UTC")),
                        flag_definition_id="REPAYMENT_HOLIDAY",
                        account_id="Main account",
                        expiry_timestamp=datetime(2019, 7, 2, tzinfo=ZoneInfo("UTC")),
                    ),
                ],
            ),
            SubTest(
                description="SCOD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (BalanceDimensions("CASH_ADVANCE_BILLED"), Decimal("1000")),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("50"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("29.70"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("2000")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("100")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("3179.70"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("3179.70"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repayment 1",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500",
                        event_datetime=datetime(2019, 2, 1, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 1, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_BILLED"),
                                Decimal("679.70"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("2000")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("2679.70"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2679.70"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="PDD 1",
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 1, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_BILLED"),
                                Decimal("679.70"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("2000")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("2679.70"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2729.45"),
                            ),
                            (
                                BalanceDimensions("LATE_REPAYMENT_FEES_CHARGED"),
                                Decimal("0"),
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="Repayment 2",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="400",
                        event_datetime=datetime(2019, 2, 26, 2, tzinfo=ZoneInfo("UTC")),
                    )
                ],
                expected_balances_at_ts={
                    datetime(2019, 2, 26, 2, tzinfo=ZoneInfo("UTC")): {
                        "Main account": [
                            (
                                BalanceDimensions("CASH_ADVANCE_BILLED"),
                                Decimal("279.70"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_FEES_BILLED"),
                                Decimal("0"),
                            ),
                            (
                                BalanceDimensions("CASH_ADVANCE_INTEREST_BILLED"),
                                Decimal("0"),
                            ),
                            (BalanceDimensions("PURCHASE_BILLED"), Decimal("2000")),
                            (BalanceDimensions("MAD_BALANCE"), Decimal("0")),
                            (BalanceDimensions("ANNUAL_FEES_BILLED"), Decimal("0")),
                            (
                                BalanceDimensions("OUTSTANDING_BALANCE"),
                                Decimal("2279.70"),
                            ),
                            (
                                BalanceDimensions("FULL_OUTSTANDING_BALANCE"),
                                Decimal("2329.45"),
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
