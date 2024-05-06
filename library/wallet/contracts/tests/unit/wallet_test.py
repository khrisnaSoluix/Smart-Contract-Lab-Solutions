# standard libs
from datetime import datetime, timedelta
from decimal import Decimal
from json import dumps
from typing import Dict, List, Optional, Tuple, Union

# common
from inception_sdk.vault.contracts.types_extension import (
    Balance,
    BalanceDefaultDict,
    Tside,
    Phase,
    Rejected,
    RejectedReason,
)
from inception_sdk.test_framework.contracts.unit.common import ContractTest, balance_dimensions

CONTRACT_FILE = "library/wallet/contracts/wallet.py"
UTILS_MODULE_FILE = "library/common/contract_modules/utils.py"
DEFAULT_DATE = datetime(2019, 1, 1)
DEFAULT_DENOMINATION = "SGD"
DECIMAL_ZERO = Decimal(0)


DEFAULT_CUSTOMER_WALLET_LIMIT = Decimal("1000")
DEFAULT_NOMINATED_ACCOUNT = "Some Account"
DEFAULT_INTERNAL_ACCOUNT = "1"
DEFAULT_DAILY_SPENDING_LIMIT = Decimal("100")
DEFAULT_ADDITIONAL_DENOMINATIONS = dumps(["GBP", "USD"])

DEFAULT_ZERO_OUT_DAILY_SPEND_HOUR = 23
DEFAULT_ZERO_OUT_DAILY_SPEND_MINUTE = 59
DEFAULT_ZERO_OUT_DAILY_SPEND_SECOND = 59


class WalletTest(ContractTest):
    contract_file = CONTRACT_FILE
    side = Tside.LIABILITY
    default_denom = DEFAULT_DENOMINATION
    linked_contract_modules = {
        "utils": {
            "path": UTILS_MODULE_FILE,
        }
    }

    def create_mock(
        self,
        balance_ts=None,
        postings=None,
        creation_date=DEFAULT_DATE,
        client_transaction=None,
        flags=None,
        denomination=DEFAULT_DENOMINATION,
        customer_wallet_limit=DEFAULT_CUSTOMER_WALLET_LIMIT,
        nominated_account=DEFAULT_NOMINATED_ACCOUNT,
        daily_spending_limit=DEFAULT_DAILY_SPENDING_LIMIT,
        additional_denominations=DEFAULT_ADDITIONAL_DENOMINATIONS,
        zero_out_daily_spend_hour=DEFAULT_ZERO_OUT_DAILY_SPEND_HOUR,
        zero_out_daily_spend_minute=DEFAULT_ZERO_OUT_DAILY_SPEND_MINUTE,
        zero_out_daily_spend_second=DEFAULT_ZERO_OUT_DAILY_SPEND_SECOND,
    ):
        if not balance_ts:
            balance_ts = []

        if not postings:
            postings = []

        if not client_transaction:
            client_transaction = {}

        if not flags:
            flags = []

        params = {
            key: {"value": value}
            for key, value in locals().items()
            if key not in self.locals_to_ignore
        }
        parameter_ts = self.param_map_to_timeseries(params, creation_date)
        return super().create_mock(
            balance_ts=balance_ts,
            parameter_ts=parameter_ts,
            postings=postings,
            creation_date=creation_date,
            client_transaction=client_transaction,
            flags=flags,
        )

    def account_balances(
        self,
        dt=DEFAULT_DATE,
        balance_defs: Optional[List[Dict[str, str]]] = None,
        default_committed: Union[int, str, Decimal] = DECIMAL_ZERO,
        todays_spending: Union[int, str, Decimal] = DECIMAL_ZERO,
        duplication: Union[int, str, Decimal] = DECIMAL_ZERO,
        default_pending_out: Union[int, str, Decimal] = DECIMAL_ZERO,
        default_pending_in: Union[int, str, Decimal] = DECIMAL_ZERO,
    ) -> List[Tuple[datetime, BalanceDefaultDict]]:

        balances = BalanceDefaultDict(
            lambda: Balance(),
            {
                balance_dimensions(denomination=DEFAULT_DENOMINATION): Balance(
                    net=default_committed
                ),
                balance_dimensions(
                    address="todays_spending", denomination=DEFAULT_DENOMINATION
                ): Balance(net=todays_spending),
                balance_dimensions(
                    address="duplication",
                    denomination=DEFAULT_DENOMINATION,
                ): Balance(net=duplication),
                balance_dimensions(
                    denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_OUT
                ): Balance(net=default_pending_out),
                balance_dimensions(
                    denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_IN
                ): Balance(net=default_pending_in),
            },
        )

        balance_defs_dict = self.init_balances(dt, balance_defs)[0][1]

        return [(dt, balances + balance_defs_dict)]

    def test_post_parameter_change_code_no_sweep_customer_limit(self):
        mock_vault = self.create_mock()

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"customer_wallet_limit": Decimal("1000")},
            updated_parameter_values={"customer_wallet_limit": Decimal("500")},
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_post_parameter_change_code_sweep_customer_limit(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("1000")
        )

        mock_vault = self.create_mock(balance_ts=balance_ts)

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"customer_wallet_limit": Decimal("1000")},
            updated_parameter_values={"customer_wallet_limit": Decimal("500")},
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_with(
            amount=Decimal("500"),
            asset="COMMERCIAL_BANK_MONEY",
            client_transaction_id="SWEEP_EXCESS_FUNDS_MOCK_HOOK",
            denomination="SGD",
            from_account_address="DEFAULT",
            from_account_id="Main account",
            instruction_details={"description": "Sweeping excess funds after limit change"},
            to_account_address="DEFAULT",
            to_account_id="Some Account",
        )

    def test_post_parameter_change_code_no_sweep_customer_limit_if_new_limit_gt(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("1000")
        )

        mock_vault = self.create_mock(balance_ts=balance_ts)

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"customer_wallet_limit": Decimal("1000")},
            updated_parameter_values={"customer_wallet_limit": Decimal("1500")},
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_post_parameter_change_no_sweep_customer_limit_if_different_param_changed(
        self,
    ):
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("1000")
        )

        mock_vault = self.create_mock(balance_ts=balance_ts)

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameter_values={"nominated_account": "1"},
            updated_parameter_values={"nominated_account": "2"},
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_pre_posting_code_rejects_if_not_enough_money(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("98")
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
        )

        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_hard_settlement(denomination="SGD", amount="99")],
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=test_postings,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(e.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)

    def test_pre_posting_code_ignores_limits_with_withdrawal_override_true(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("98")
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
        )
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_hard_settlement(denomination="SGD", amount="99")],
            batch_details={"withdrawal_override": "true"},
        )
        try:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=test_postings,
                effective_date=DEFAULT_DATE,
            )
        except Exception as e:
            self.fail("pre_posting_code raised exception " + str(e))

    def test_pre_posting_code_checks_denominations_with_withdrawal_override_true(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("98")
        )

        mock_vault = self.create_mock(balance_ts=balance_ts)
        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_hard_settlement(denomination="XYZ", amount="99")],
            batch_details={"withdrawal_override": "true"},
        )
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=test_postings,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(e.exception.reason_code, RejectedReason.WRONG_DENOMINATION)

    def test_pre_posting_code_rejects_if_over_limit(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("200")
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            daily_spending_limit=Decimal("100"),
        )

        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_hard_settlement(denomination="SGD", amount="200")],
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=test_postings,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)

    def test_post_posting_code_duplicates_spending(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("200")
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            daily_spending_limit=Decimal("100"),
        )

        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_hard_settlement(denomination="SGD", amount="200")],
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=test_postings,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("200"),
            asset="COMMERCIAL_BANK_MONEY",
            client_transaction_id="UPDATING_TRACKED_SPEND-MOCK_HOOK",
            denomination="SGD",
            from_account_address="todays_spending",
            from_account_id="Main account",
            to_account_address="duplication",
            to_account_id="Main account",
        )

        mock_vault.instruct_posting_batch.assert_called_once_with(
            effective_date=datetime(2019, 1, 1, 0, 0),
            posting_instructions=["UPDATING_TRACKED_SPEND-MOCK_HOOK"],
        )

    def test_post_posting_code_doesnt_duplicate_spending_with_withdrawal_override_true(
        self,
    ):
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("200")
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            daily_spending_limit=Decimal("100"),
        )

        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[self.outbound_hard_settlement(denomination="SGD", amount="200")],
            batch_details={"withdrawal_override": "true"},
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=test_postings,
            effective_date=DEFAULT_DATE,
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_post_posting_code_duplicates_release_with_withdrawal_override_true(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("200")
        )

        mock_vault = self.create_mock(balance_ts=balance_ts, daily_spending_limit=Decimal("100"))

        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.release_outbound_auth(unsettled_amount=Decimal(10)),
            ],
            batch_details={"withdrawal_override": "true"},
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=test_postings,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("10"),
            asset="COMMERCIAL_BANK_MONEY",
            client_transaction_id="UPDATING_TRACKED_SPEND-MOCK_HOOK",
            denomination="SGD",
            from_account_address="duplication",
            from_account_id="Main account",
            to_account_address="todays_spending",
            to_account_id="Main account",
        )

        mock_vault.instruct_posting_batch.assert_called_once_with(
            effective_date=datetime(2019, 1, 1, 0, 0),
            posting_instructions=["UPDATING_TRACKED_SPEND-MOCK_HOOK"],
        )

    def test_post_posting_code_sweeps_over_balance(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("10000")
        )

        mock_vault = self.create_mock(balance_ts=balance_ts, daily_spending_limit=Decimal("100"))

        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    denomination="SGD",
                    amount=Decimal("10000"),
                )
            ],
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=test_postings,
            effective_date=DEFAULT_DATE,
        )

        # As unit test won't get balance.before() posting, the amount here
        # is changed to 19000 instead of 9000, as the logic in SC count make
        # the unit test count posting twice.
        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("19000"),
            asset="COMMERCIAL_BANK_MONEY",
            client_transaction_id="RETURNING_EXCESS_BALANCE_MOCK_HOOK",
            denomination="SGD",
            from_account_address="DEFAULT",
            from_account_id="Main account",
            to_account_address="DEFAULT",
            to_account_id="Some Account",
        )

        mock_vault.instruct_posting_batch.assert_called_once_with(
            effective_date=datetime(2019, 1, 1, 0, 0),
            posting_instructions=["RETURNING_EXCESS_BALANCE_MOCK_HOOK"],
        )

    def test_close_code_zeros_daily_spend_amount(self):

        balances_ts = self.account_balances(todays_spending=-100, duplication=100)

        mock_vault = self.create_mock(balance_ts=balances_ts)

        self.run_function(
            "close_code",
            mock_vault,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("100"),
            asset="COMMERCIAL_BANK_MONEY",
            client_transaction_id="UPDATING_TRACKED_SPEND-MOCK_HOOK",
            denomination="SGD",
            from_account_address="duplication",
            from_account_id="Main account",
            to_account_address="todays_spending",
            to_account_id="Main account",
        )

        mock_vault.instruct_posting_batch.assert_called_once_with(
            client_batch_id="ZERO_OUT_DAILY_SPENDING-MOCK_HOOK",
            effective_date=datetime(2019, 1, 1, 0, 0),
            posting_instructions=["UPDATING_TRACKED_SPEND-MOCK_HOOK"],
            batch_details={"event_type": "ZERO_OUT_DAILY_SPENDING"},
        )

    def test_close_code_no_daily_spending(self):

        balances_ts = self.account_balances()

        mock_vault = self.create_mock(balance_ts=balances_ts)
        self.run_function(
            "close_code",
            mock_vault,
            effective_date=DEFAULT_DATE,
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_close_code_on_default_address_amount(self):

        balances_ts = self.account_balances(default_committed=100)
        mock_vault = self.create_mock(balance_ts=balances_ts)
        self.run_function(
            "close_code",
            mock_vault,
            effective_date=DEFAULT_DATE,
        )
        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()

    def test_execution_schedules_returns_correct_schedule(self):
        mock_vault = self.create_mock(
            zero_out_daily_spend_hour=23,
            zero_out_daily_spend_minute=59,
            zero_out_daily_spend_second=59,
        )
        res = self.run_function("execution_schedules", mock_vault)
        zero_out_daily_spend_schedule = {"hour": "23", "minute": "59", "second": "59"}
        self.assertEqual(
            res,
            [("ZERO_OUT_DAILY_SPEND", zero_out_daily_spend_schedule)],
        )

    def test_scheduled_code_zeros_out_daily_spend(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1),
            default_committed=Decimal("200"),
            todays_spending=Decimal("-100"),
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
        )

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ZERO_OUT_DAILY_SPEND",
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal("100"),
            asset="COMMERCIAL_BANK_MONEY",
            client_transaction_id="UPDATING_TRACKED_SPEND-MOCK_HOOK",
            denomination="SGD",
            from_account_address="duplication",
            from_account_id="Main account",
            to_account_address="todays_spending",
            to_account_id="Main account",
        )

        mock_vault.instruct_posting_batch.assert_called_once_with(
            client_batch_id="ZERO_OUT_DAILY_SPENDING-MOCK_HOOK",
            effective_date=datetime(2019, 1, 1, 0, 0),
            posting_instructions=["UPDATING_TRACKED_SPEND-MOCK_HOOK"],
            batch_details={"event_type": "ZERO_OUT_DAILY_SPENDING"},
        )

    def test_posting_batch_with_additional_denom_and_sufficient_balance_is_accepted(
        self,
    ):

        additional_denominations = ["GBP"]
        gbp_posting = self.outbound_hard_settlement(amount="30", denomination="GBP")

        mock_vault = self.create_mock(
            balance_ts=self.account_balances(
                DEFAULT_DATE - timedelta(days=1),
                balance_defs=[{"address": "default", "denomination": "GBP", "net": "100"}],
            ),
            denomination=DEFAULT_DENOMINATION,
            additional_denominations=dumps(additional_denominations),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[gbp_posting])

        try:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                DEFAULT_DATE,
            )
        except Rejected:
            self.fail("pre_posting_code doesn't allow movement of funds out")
        except Exception as e:
            self.fail(f"Unexpected error raised in pre_posting_code: {e}")

    def test_posting_batch_with_additional_denom_and_sufficient_balances_is_accepted(
        self,
    ):

        additional_denominations = ["GBP", "USD"]
        usd_posting = self.outbound_hard_settlement(amount="20", denomination="USD")
        gbp_posting = self.outbound_hard_settlement(amount="30", denomination="GBP")

        mock_vault = self.create_mock(
            balance_ts=self.account_balances(
                balance_defs=[
                    {"address": "default", "denomination": "USD", "net": "100"},
                    {"address": "default", "denomination": "GBP", "net": "100"},
                ]
            ),
            additional_denominations=dumps(additional_denominations),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[usd_posting, gbp_posting])

        try:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                DEFAULT_DATE,
            )
        except Rejected:
            self.fail("pre_posting_code doesn't allow movement of funds out")
        except Exception as e:
            self.fail(f"Unexpected error raised in pre_posting_code: {e}")

    def test_posting_batch_with_single_denom_rejected_if_insufficient_balances(self):

        additional_denominations = ["USD"]
        usd_posting = self.outbound_hard_settlement(amount="20", denomination="USD")

        mock_vault = self.create_mock(
            balance_ts=self.account_balances(
                balance_defs=[
                    {"address": "default", "denomination": "USD", "net": "10"},
                ]
            ),
            additional_denominations=dumps(additional_denominations),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[usd_posting])

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                DEFAULT_DATE,
            )

        expected_rejection_error = (
            "Postings total USD -20, which exceeds the available balance of USD 10"
        )

        self.assertEqual(str(e.exception), expected_rejection_error)
        self.assertEqual(e.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)

    def test_posting_batch_with_supported_and_unsupported_denom_is_rejected(self):

        additional_denominations = ["GBP", "USD"]
        hkd_posting = self.outbound_hard_settlement(denomination="HKD", amount=1)
        usd_posting = self.outbound_hard_settlement(denomination="USD", amount=1)
        zar_posting = self.outbound_hard_settlement(denomination="ZAR", amount=1)
        gbp_posting = self.outbound_hard_settlement(denomination="GBP", amount=1)

        mock_vault = self.create_mock(
            balance_ts=self.account_balances(),
            additional_denominations=dumps(additional_denominations),
        )

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[hkd_posting, usd_posting, zar_posting, gbp_posting]
        )

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                DEFAULT_DATE,
            )

        expected_rejection_error = "Postings received in unauthorised denominations"

        self.assertEqual(str(e.exception), expected_rejection_error)
        self.assertEqual(e.exception.reason_code, RejectedReason.WRONG_DENOMINATION)

    def test_posting_batch_with_single_unsupported_denom_is_rejected(self):

        additional_denominations = ["GBP", "USD"]
        posting = self.outbound_hard_settlement(denomination="HKD", amount=1)

        mock_vault = self.create_mock(
            balance_ts=self.account_balances(),
            additional_denominations=dumps(additional_denominations),
        )

        pib = self.mock_posting_instruction_batch(posting_instructions=[posting])

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                pib,
                DEFAULT_DATE,
            )

        expected_rejection_error = "Postings received in unauthorised denominations"
        self.assertEqual(str(e.exception), expected_rejection_error)
        self.assertEqual(e.exception.reason_code, RejectedReason.WRONG_DENOMINATION)

    def test_pre_posting_no_money_flag_false(self):
        effective_time = datetime(2020, 1, 1)
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("0")
        )
        posting_instructions = []
        posting_instructions.append(
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("100"))
        )

        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=posting_instructions
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            nominated_account="Some Account",
        )

        with self.assertRaises(Rejected) as e:
            self.run_function("pre_posting_code", mock_vault, test_postings, effective_time)
        self.assertEqual(e.exception.reason_code, RejectedReason.INSUFFICIENT_FUNDS)

    def test_pre_posting_no_money_flag_true(self):
        balance_ts = self.account_balances(
            DEFAULT_DATE - timedelta(days=1), default_committed=Decimal("0")
        )
        posting_instructions = []
        posting_instructions.append(
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("100"))
        )

        test_postings = self.mock_posting_instruction_batch(
            posting_instructions=posting_instructions
        )

        mock_vault = self.create_mock(
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
            nominated_account="Some Account",
            flags=["AUTO_TOP_UP_WALLET"],
        )

        try:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=test_postings,
                effective_date=DEFAULT_DATE,
            )
        except Rejected:
            self.fail("pre_posting_code doesn't allow movement of funds out")
        except Exception as e:
            self.fail(f"Unexpected error raised in pre_posting_code: {e}")

    def test_available_balance_zero_if_all_balances_zero(self):
        balances = self.account_balances(
            default_committed=Decimal(0), default_pending_out=Decimal(0)
        )[0][1]

        available_balance = self.run_function(
            function_name="_available_balance",
            vault_object=None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(available_balance, Decimal(0))

    def test_pending_out_subtracted_from_available_balance(self):
        balances = self.account_balances(
            default_committed=Decimal(2), default_pending_out=Decimal(-1)
        )[0][1]

        available_balance = self.run_function(
            function_name="_available_balance",
            vault_object=None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(available_balance, Decimal(1))

    def test_pending_in_has_no_impact_on_available_balance(self):
        balances = self.account_balances(
            default_committed=Decimal(2),
            default_pending_out=Decimal(-1),
            default_pending_in=Decimal(100),
        )[0][1]

        available_balance = self.run_function(
            function_name="_available_balance",
            vault_object=None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(available_balance, Decimal(1))

    def test_release_and_decreased_auth_includes_releases_and_decreased_outbound_auths(
        self,
    ):

        postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.release_outbound_auth(unsettled_amount=Decimal(10)),
                self.outbound_auth_adjust(amount=Decimal(-5)),
                # None of the below should have any impact
                self.settle_outbound_auth(
                    amount=Decimal(100), unsettled_amount=Decimal(100), final=True
                ),
                self.inbound_hard_settlement(amount=Decimal(1000)),
                self.outbound_auth_adjust(amount=Decimal(10000)),
                self.inbound_auth_adjust(amount=Decimal(100000)),
            ]
        )

        amount = self.run_function(
            function_name="_get_release_and_decreased_auth_amount",
            vault_object=None,
            postings=postings,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(amount, Decimal(15))
