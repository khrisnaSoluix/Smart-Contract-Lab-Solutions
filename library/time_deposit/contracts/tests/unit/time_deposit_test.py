# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from decimal import Decimal
from typing import List, Tuple
from unittest.mock import call

# common
from inception_sdk.test_framework.contracts.unit.common import ContractTest, balance_dimensions
from inception_sdk.vault.contracts.types_extension import (
    PostingInstruction,
    Rejected,
    Tside,
    RejectedReason,
    UnionItemValue,
    Balance,
    Phase,
    CalendarEvent,
    BalanceDefaultDict,
)

CONTRACT_FILE = "library/time_deposit/contracts/time_deposit.py"
INTEREST_MODULE_FILE = "library/common/contract_modules/interest.py"
UTILS_MODULE_FILE = "library/common/contract_modules/utils.py"
DEFAULT_DATE = datetime(2019, 1, 1)
VAULT_ACCOUNT_ID = "Main account"
DEFAULT_DENOMINATION = "GBP"
DEFAULT_ADDRESS = "DEFAULT"
DEFAULT_ASSET = "COMMERCIAL_BANK_MONEY"
ACCRUED_INTEREST_PAYABLE = "ACCRUED_INTEREST_PAYABLE"
INTERNAL_CONTRA = "INTERNAL_CONTRA"
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
CAPITALISED_INTEREST = "CAPITALISED_INTEREST"
TIME_DEPOSIT_BANK_HOLIDAY = "PUBLIC_HOLIDAYS"

default_committed = balance_dimensions(denomination=DEFAULT_DENOMINATION)
default_pending_incoming = balance_dimensions(
    denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_IN
)
default_pending_outgoing = balance_dimensions(
    denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_OUT
)
accrued_incoming_balance = balance_dimensions(
    denomination=DEFAULT_DENOMINATION, address=ACCRUED_INTEREST_PAYABLE
)
capitalised_interest_balance = balance_dimensions(
    denomination=DEFAULT_DENOMINATION, address=CAPITALISED_INTEREST
)
DEFAULT_ACCRUAL_PRECISION = 5
DEFAULT_DEPOSIT_PERIOD = 7
DEFAULT_FULFILLMENT_PRECISION = 2
DEFAULT_GRACE_PERIOD = 0
DEFAULT_ACCOUNT_CLOSURE_PERIOD = 7
PERIOD_end_hour = 21

DEFAULT_GROSS_INTEREST_RATE = Decimal("0.149")
DEFAULT_INTEREST_ACCRUAL_HOUR = 23
DEFAULT_INTEREST_ACCRUAL_MINUTE = 59
DEFAULT_INTEREST_ACCRUAL_SECOND = 59
DEFAULT_INTEREST_APPLICATION_DAY = 1
DEFAULT_INTEREST_APPLICATION_FREQUENCY = UnionItemValue(key="monthly")
DEFAULT_INTEREST_APPLICATION_HOUR = 23
DEFAULT_INTEREST_APPLICATION_MINUTE = 59
DEFAULT_INTEREST_APPLICATION_SECOND = 59
DEFAULT_MAXIMUM_BALANCE = Decimal("100000")
DEFAULT_MINIMUM_FIRST_DEPOSIT = Decimal("50")
DEFAULT_SINGLE_DEPOSIT = UnionItemValue(key="unlimited")
DEFAULT_TERM = 12


class TimeDepositTest(ContractTest):
    contract_file = CONTRACT_FILE
    side = Tside.LIABILITY
    linked_contract_modules = {
        "interest": {
            "path": INTEREST_MODULE_FILE,
        },
        "utils": {
            "path": UTILS_MODULE_FILE,
        },
    }

    def create_mock(
        self,
        balance_ts=None,
        postings=None,
        creation_date=None,
        client_transaction=None,
        flags=None,
        accrual_precision=DEFAULT_ACCRUAL_PRECISION,
        denomination=DEFAULT_DENOMINATION,
        deposit_period=DEFAULT_DEPOSIT_PERIOD,
        fulfillment_precision=DEFAULT_FULFILLMENT_PRECISION,
        grace_period=DEFAULT_GRACE_PERIOD,
        period_end_hour=PERIOD_end_hour,
        account_closure_period=DEFAULT_ACCOUNT_CLOSURE_PERIOD,
        gross_interest_rate=DEFAULT_GROSS_INTEREST_RATE,
        interest_accrual_hour=DEFAULT_INTEREST_ACCRUAL_HOUR,
        interest_accrual_minute=DEFAULT_INTEREST_ACCRUAL_MINUTE,
        interest_accrual_second=DEFAULT_INTEREST_ACCRUAL_SECOND,
        interest_application_day=DEFAULT_INTEREST_APPLICATION_DAY,
        interest_application_frequency=DEFAULT_INTEREST_APPLICATION_FREQUENCY,
        interest_application_hour=DEFAULT_INTEREST_APPLICATION_HOUR,
        interest_application_minute=DEFAULT_INTEREST_APPLICATION_MINUTE,
        interest_application_second=DEFAULT_INTEREST_APPLICATION_SECOND,
        maximum_balance=DEFAULT_MAXIMUM_BALANCE,
        minimum_first_deposit=DEFAULT_MINIMUM_FIRST_DEPOSIT,
        single_deposit=DEFAULT_SINGLE_DEPOSIT,
        term=DEFAULT_TERM,
        accrued_interest_payable_account=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
        interest_paid_account=INTEREST_PAID_ACCOUNT,
        **kwargs,
    ):
        params = {
            key: {"value": value}
            for key, value in locals().items()
            if key not in self.locals_to_ignore
        }
        if not creation_date:
            creation_date = DEFAULT_DATE

        parameter_ts = self.param_map_to_timeseries(params, creation_date)
        return super().create_mock(
            balance_ts=balance_ts if balance_ts else [],
            parameter_ts=parameter_ts,
            postings=postings if postings else [],
            creation_date=creation_date,
            client_transaction=client_transaction if client_transaction else {},
            flags=flags if flags else [],
            **kwargs,
        )

    def account_balances(
        self,
        dt=DEFAULT_DATE,
        default_committed=Decimal("0"),
        accrued_incoming=Decimal("0"),
        default_pending_incoming=Decimal("0"),
        default_pending_outgoing=Decimal("0"),
        capitalised_interest=Decimal("0"),
    ) -> List[Tuple[datetime, BalanceDefaultDict]]:

        balance_dict = {
            balance_dimensions(denomination=DEFAULT_DENOMINATION): Balance(net=default_committed),
            balance_dimensions(denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_OUT): Balance(
                net=default_pending_outgoing
            ),
            balance_dimensions(denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_IN): Balance(
                net=default_pending_incoming
            ),
            balance_dimensions(
                denomination=DEFAULT_DENOMINATION, address=ACCRUED_INTEREST_PAYABLE
            ): Balance(net=accrued_incoming),
            balance_dimensions(
                denomination=DEFAULT_DENOMINATION, address=CAPITALISED_INTEREST
            ): Balance(net=capitalised_interest),
        }

        balance_default_dict = BalanceDefaultDict(lambda: Balance(net=Decimal("0")), balance_dict)

        return [(dt, balance_default_dict)]

    def test_pre_posting_code_rejects_wrong_denomination_single_posting(self):
        mock_vault = self.create_mock(denomination=DEFAULT_DENOMINATION)

        postings = [PostingInstruction(denomination="USD")]

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=postings,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(e.exception),
            f"Cannot make transactions in given denomination; "
            f"transactions must be in {DEFAULT_DENOMINATION}",
        )

        self.assertEqual(e.exception.reason_code, RejectedReason.WRONG_DENOMINATION)

    def test_pre_posting_code_rejects_wrong_denomination_multi_postings(self):
        mock_vault = self.create_mock(denomination=DEFAULT_DENOMINATION)

        postings = [
            PostingInstruction(denomination="GBP"),
            PostingInstruction(denomination="USD"),
        ]

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=postings,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            str(e.exception),
            f"Cannot make transactions in given denomination; "
            f"transactions must be in {DEFAULT_DENOMINATION}",
        )

        self.assertEqual(e.exception.reason_code, RejectedReason.WRONG_DENOMINATION)

    def test_pre_posting_code_rejects_deposit_less_than_minimum_amount(self):
        balances_ts = self.account_balances()
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            minimum_first_deposit=Decimal(50),
            maximum_balance=Decimal(1000),
            single_deposit=UnionItemValue("unlimited"),
            balance_ts=balances_ts,
            term_unit=UnionItemValue("months"),
            term=1,
            cool_off_period=0,
            deposit_period=7,
        )
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal(49))
        ]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=datetime(2019, 1, 7),
            )

        self.assertEqual(
            str(e.exception),
            f"Deposit amount less than minimum first deposit amount " f"50 {DEFAULT_DENOMINATION}",
        )
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)

    def test_pre_posting_code_rejects_deposit_lt_minimum_amount_decimal(self):
        balances_ts = self.account_balances()
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            minimum_first_deposit=Decimal("50.01"),
            maximum_balance=Decimal(1000),
            single_deposit=UnionItemValue("unlimited"),
            deposit_period=28,
            term_unit=UnionItemValue("months"),
            term=1,
            cool_off_period=0,
            balance_ts=balances_ts,
        )
        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal("49.99"))
        ]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=datetime(2019, 1, 7),
            )

        self.assertEqual(
            str(e.exception),
            f"Deposit amount less than minimum first deposit amount "
            f'{Decimal("50.01")} {DEFAULT_DENOMINATION}',
        )
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)

    def test_pre_posting_code_rejects_deposit_over_max_balance(self):
        balances_ts = self.account_balances(default_committed=Decimal(99))
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            minimum_first_deposit=Decimal("50.01"),
            maximum_balance=Decimal(100),
            single_deposit=UnionItemValue("unlimited"),
            deposit_period=28,
            term_unit=UnionItemValue("months"),
            term=1,
            cool_off_period=0,
            balance_ts=balances_ts,
        )

        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal(2))
        ]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )
        self.assertEqual(str(e.exception), "Posting would cause maximum balance to be exceeded")
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)

    def test_pre_posting_code_rejects_withdrawal_more_than_available_balance(self):
        balances_ts = self.account_balances(default_committed=Decimal(100))
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            minimum_first_deposit=Decimal("50.01"),
            maximum_balance=Decimal(100),
            single_deposit=UnionItemValue("unlimited"),
            deposit_period=28,
            term_unit=UnionItemValue("months"),
            term=1,
            cool_off_period=0,
            balance_ts=balances_ts,
        )

        postings = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal(101))
        ]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )
        self.assertEqual(str(e.exception), "Transaction cannot bring available balance below 0")

    def test_pre_posting_code_withdrawal_on_creation_date(
        self,
    ):
        balances_ts = self.account_balances(default_committed=Decimal(100))
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            minimum_first_deposit=Decimal("50.00"),
            maximum_balance=Decimal(100),
            single_deposit=UnionItemValue("unlimited"),
            deposit_period=5,
            term_unit=UnionItemValue("months"),
            term=1,
            cool_off_period=0,
            grace_period=0,
            period_end_hour=0,
            balance_ts=balances_ts,
        )

        postings = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal(50)),
        ]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)

        # Rejected since no values were given for grace preiod,
        # general close hour and cool off period
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=datetime(2019, 1, 1, 0),
            )
        self.assertEqual(
            str(e.exception),
            "Withdrawal value_timestamp 2019-01-01 00:00:00 is greater than maximum withdrawal date"
            + " 2019-01-01 00:00:00",
        )

    def test_pre_posting_code_rejects_withdrawal_more_than_available_balance_with_po(
        self,
    ):
        balances_ts = self.account_balances(
            default_committed=Decimal(100), default_pending_outgoing=Decimal(-100)
        )
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            minimum_first_deposit=Decimal("50.01"),
            maximum_balance=Decimal(100),
            single_deposit=UnionItemValue("unlimited"),
            deposit_period=28,
            deposit_period_end_time=21,
            term_unit=UnionItemValue("months"),
            term=1,
            cool_off_period=0,
            grace_period=0,
            balance_ts=balances_ts,
        )

        postings = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal(1))
        ]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )
        self.assertEqual(str(e.exception), "Transaction cannot bring available balance below 0")

    def test_pre_posting_code_withdrawal_on_grace_period(
        self,
    ):
        balances_ts = self.account_balances(default_committed=Decimal(100))
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            minimum_first_deposit=Decimal("50.00"),
            maximum_balance=Decimal(100),
            single_deposit=UnionItemValue("unlimited"),
            deposit_period=0,
            term_unit=UnionItemValue("months"),
            term=1,
            cool_off_period=0,
            grace_period=10,
            period_end_hour=7,
            balance_ts=balances_ts,
        )

        postings = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal(50)),
        ]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        # Rejected outside grace period
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=datetime(2019, 1, 11, 7),
            )
        self.assertEqual(
            str(e.exception),
            "Withdrawal value_timestamp 2019-01-11 07:00:00 is greater than maximum withdrawal date"
            + " 2019-01-11 07:00:00",
        )
        # Allowed inside grace period
        self.run_function(
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=datetime(2019, 1, 11, 6, 59, 59),
        )

    def test_pre_posting_code_withdrawal_on_deposit_period(
        self,
    ):
        balances_ts = self.account_balances(default_committed=Decimal(100))
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            minimum_first_deposit=Decimal("50.00"),
            maximum_balance=Decimal(100),
            single_deposit=UnionItemValue("unlimited"),
            deposit_period=5,
            term_unit=UnionItemValue("months"),
            term=1,
            cool_off_period=0,
            grace_period=0,
            period_end_hour=3,
            balance_ts=balances_ts,
        )

        postings = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal(50)),
        ]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        # Rejected outside deposit period
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=datetime(2019, 1, 6, 3, 59, 59),
            )
        self.assertEqual(
            str(e.exception),
            "Withdrawal value_timestamp 2019-01-06 03:59:59 is greater than maximum withdrawal date"
            + " 2019-01-01 03:00:00",
        )
        # Rejected inside deposit period
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=datetime(2019, 1, 6, 2, 59, 59),
            )
        self.assertEqual(
            str(e.exception),
            "Withdrawal value_timestamp 2019-01-06 02:59:59 is greater than maximum withdrawal date"
            + " 2019-01-01 03:00:00",
        )
        # Rejected outside general close hour
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=datetime(2019, 1, 1, 3),
            )
        self.assertEqual(
            str(e.exception),
            "Withdrawal value_timestamp 2019-01-01 03:00:00 is greater than maximum withdrawal date"
            + " 2019-01-01 03:00:00",
        )
        # Allowed since its inside the general close hour
        self.run_function(
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=datetime(2019, 1, 1, 2, 59, 59),
        )

    def test_pre_posting_code_withdrawal_on_cool_off_period(
        self,
    ):
        balances_ts = self.account_balances(default_committed=Decimal(100))
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            minimum_first_deposit=Decimal("50.00"),
            maximum_balance=Decimal(100),
            single_deposit=UnionItemValue("unlimited"),
            deposit_period=5,
            term_unit=UnionItemValue("months"),
            term=1,
            cool_off_period=9,
            grace_period=0,
            period_end_hour=2,
            balance_ts=balances_ts,
        )

        postings = [
            self.outbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal(50)),
        ]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        # Rejected outside cool off period
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=datetime(2019, 1, 10, 2),
            )
        self.assertEqual(
            str(e.exception),
            "Withdrawal value_timestamp 2019-01-10 02:00:00 is greater than maximum withdrawal date"
            + " 2019-01-10 02:00:00",
        )
        # Allowed inside cool off period
        self.run_function(
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=datetime(2019, 1, 10, 1, 59, 59),
        )

    def test_pre_posting_code_deposit_on_creation_date(
        self,
    ):
        balances_ts = self.account_balances()
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            minimum_first_deposit=Decimal("50.00"),
            maximum_balance=Decimal(100),
            single_deposit=UnionItemValue("unlimited"),
            deposit_period=0,
            term_unit=UnionItemValue("months"),
            term=1,
            cool_off_period=0,
            grace_period=0,
            period_end_hour=0,
            balance_ts=balances_ts,
        )

        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal(50)),
        ]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)

        # Rejected since no values were given for deposit period, grace preiod,
        # general close hour and cool off period
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=datetime(2019, 1, 1, 0),
            )
        self.assertEqual(
            str(e.exception),
            "Deposit value_timestamp 2019-01-01 00:00:00 is greater than maximum deposit date"
            + " 2019-01-01 00:00:00",
        )

    def test_pre_posting_code_deposit_on_grace_period(
        self,
    ):
        balances_ts = self.account_balances()
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            minimum_first_deposit=Decimal("50.00"),
            maximum_balance=Decimal(100),
            single_deposit=UnionItemValue("unlimited"),
            deposit_period=0,
            term_unit=UnionItemValue("months"),
            term=1,
            cool_off_period=0,
            grace_period=10,
            period_end_hour=0,
            balance_ts=balances_ts,
        )

        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal(50)),
        ]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        # Rejected outside grace period
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=datetime(2019, 1, 11, 0, 59, 59),
            )
        self.assertEqual(
            str(e.exception),
            "Deposit value_timestamp 2019-01-11 00:59:59 is greater than maximum deposit date"
            + " 2019-01-11 00:00:00",
        )
        # Allowed inside grace period
        self.run_function(
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=datetime(2019, 1, 10, 23, 59, 59),
        )

    def test_pre_posting_code_deposit_on_deposit_period(
        self,
    ):
        balances_ts = self.account_balances()
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            minimum_first_deposit=Decimal("50.00"),
            maximum_balance=Decimal(100),
            single_deposit=UnionItemValue("unlimited"),
            deposit_period=5,
            term_unit=UnionItemValue("months"),
            term=1,
            cool_off_period=0,
            grace_period=0,
            period_end_hour=3,
            balance_ts=balances_ts,
        )

        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal(50)),
        ]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        # Rejected outside deposit period
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=datetime(2019, 1, 6, 3),
            )
        self.assertEqual(
            str(e.exception),
            "Deposit value_timestamp 2019-01-06 03:00:00 is greater than maximum deposit date"
            + " 2019-01-06 03:00:00",
        )
        # Allowed inside deposit period
        self.run_function(
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=datetime(2019, 1, 6, 2, 23, 59, 59),
        )

    def test_pre_posting_code_deposit_on_cool_off_period(
        self,
    ):
        balances_ts = self.account_balances()
        mock_vault = self.create_mock(
            creation_date=datetime(2019, 1, 1),
            denomination=DEFAULT_DENOMINATION,
            minimum_first_deposit=Decimal("50.00"),
            maximum_balance=Decimal(100),
            single_deposit=UnionItemValue("unlimited"),
            deposit_period=5,
            term_unit=UnionItemValue("months"),
            term=1,
            cool_off_period=9,
            grace_period=0,
            period_end_hour=2,
            balance_ts=balances_ts,
        )

        postings = [
            self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount=Decimal(50)),
        ]
        pib = self.mock_posting_instruction_batch(posting_instructions=postings)
        # Rejected outside cool off period
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=datetime(2019, 1, 10, 2),
            )
        self.assertEqual(
            str(e.exception),
            "Deposit value_timestamp 2019-01-10 02:00:00 is greater than maximum deposit date"
            + " 2019-01-10 02:00:00",
        )
        # Allowed inside cool off period
        self.run_function(
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=datetime(2019, 1, 10, 1, 59, 59),
        )

    def test_post_parameter_change_code_monthly_before_application(self):
        mock_vault = self.create_mock(
            interest_application_frequency=UnionItemValue(key="monthly"),
            interest_application_hour=23,
            interest_application_minute=34,
            interest_application_second=45,
            APPLY_ACCRUED_INTEREST=datetime(2020, 1, 1),
        )

        old_parameters = {"interest_application_day": 1}
        new_parameters = {"interest_application_day": 10}

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters=old_parameters,
            new_parameters=new_parameters,
            effective_date=datetime(2020, 1, 5),
        )

        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule={
                "year": "2020",
                "month": "1",
                "day": "10",
                "hour": "23",
                "minute": "34",
                "second": "45",
            },
        )

    def test_adjust_capitalised_interest(self):
        balances_ts = self.account_balances(
            default_committed=Decimal(421), capitalised_interest=Decimal(521)
        )
        mock_vault = self.create_mock(balance_ts=balances_ts)

        postings = [
            {
                "amount": Decimal("100"),
                "denomination": DEFAULT_DENOMINATION,
                "client_transaction_id": "MOVE_CAPITALISED_INTEREST_TO_INTERNAL_CONTRA_"
                + "MOCK_HOOK_GBP_CUSTOMER",
                "from_account_id": "Main account",
                "from_account_address": CAPITALISED_INTEREST,
                "to_account_id": "Main account",
                "to_account_address": INTERNAL_CONTRA,
                "instruction_details": {
                    "description": "Moving capitalised interest to internal contra",
                },
                "asset": DEFAULT_ASSET,
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in postings]

        self.run_function(
            "_adjust_capitalised_interest",
            mock_vault,
            vault=mock_vault,
            denomination=DEFAULT_DENOMINATION,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=[
                "MOVE_CAPITALISED_INTEREST_TO_INTERNAL_CONTRA_MOCK_HOOK_GBP_CUSTOMER"
            ],
            effective_date=DEFAULT_DATE,
        )

    def test_adjust_capitalised_interest_no_adjustment(self):
        balances_ts = self.account_balances(
            default_committed=Decimal(521), capitalised_interest=Decimal(521)
        )
        mock_vault = self.create_mock(balance_ts=balances_ts)

        self.run_function(
            "_adjust_capitalised_interest",
            mock_vault,
            vault=mock_vault,
            denomination=DEFAULT_DENOMINATION,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_adjust_capitalised_interest_no_capitalised_interest(self):
        balances_ts = self.account_balances(
            default_committed=Decimal(300), capitalised_interest=Decimal(0)
        )
        mock_vault = self.create_mock(balance_ts=balances_ts)

        self.run_function(
            "_adjust_capitalised_interest",
            mock_vault,
            vault=mock_vault,
            denomination=DEFAULT_DENOMINATION,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_post_posting_code_adjusts_capitalised_interest_with_no_rollover_type_specified(self):
        balances_ts = self.account_balances(
            default_committed=Decimal(421), capitalised_interest=Decimal(521)
        )
        mock_vault = self.create_mock(balance_ts=balances_ts)

        postings = [
            self.outbound_transfer(amount=Decimal("200.08")),
        ]
        pib = self.mock_posting_instruction_batch(
            posting_instructions=postings,
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        new_postings = [
            {
                "amount": Decimal("100"),
                "denomination": DEFAULT_DENOMINATION,
                "client_transaction_id": "MOVE_CAPITALISED_INTEREST_TO_INTERNAL_CONTRA_"
                + "MOCK_HOOK_GBP_CUSTOMER",
                "from_account_id": "Main account",
                "from_account_address": CAPITALISED_INTEREST,
                "to_account_id": "Main account",
                "to_account_address": INTERNAL_CONTRA,
                "instruction_details": {
                    "description": "Moving capitalised interest to internal contra",
                },
                "asset": DEFAULT_ASSET,
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in new_postings]

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=[
                "MOVE_CAPITALISED_INTEREST_TO_INTERNAL_CONTRA_MOCK_HOOK_GBP_CUSTOMER"
            ],
            effective_date=DEFAULT_DATE,
        )

    def test_post_posting_code_no_adjustment_made_with_no_rollover_type_specified(self):
        balances_ts = self.account_balances(
            default_committed=Decimal(521), capitalised_interest=Decimal(521)
        )
        mock_vault = self.create_mock(balance_ts=balances_ts)

        postings = [
            self.outbound_transfer(amount=Decimal("100")),
        ]
        pib = self.mock_posting_instruction_batch(
            posting_instructions=postings,
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_post_posting_code_no_capitalised_interest_with_no_rollover_type_specified(self):
        balances_ts = self.account_balances(
            default_committed=Decimal(521), capitalised_interest=Decimal(0)
        )
        mock_vault = self.create_mock(balance_ts=balances_ts)

        postings = [
            self.outbound_transfer(amount=Decimal("100")),
        ]
        pib = self.mock_posting_instruction_batch(
            posting_instructions=postings,
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()

    def test_post_posting_code_rollover_principal_and_interest_amount_zero_default(self):
        balances_ts = self.account_balances(
            default_committed=Decimal("0"), capitalised_interest=Decimal("0.8")
        )
        mock_vault = self.create_mock(balance_ts=balances_ts)

        postings = [
            self.outbound_transfer(amount=Decimal("200.08")),
        ]
        pib = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            batch_details={"auto_rollover_type": "principal_and_interest"},
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        new_postings = [
            {
                "amount": Decimal("0.8"),
                "denomination": DEFAULT_DENOMINATION,
                "client_transaction_id": "MOVE_CAPITALISED_INTEREST_TO_INTERNAL_CONTRA_"
                + "MOCK_HOOK_GBP_CUSTOMER",
                "from_account_id": "Main account",
                "from_account_address": CAPITALISED_INTEREST,
                "to_account_id": "Main account",
                "to_account_address": INTERNAL_CONTRA,
                "instruction_details": {
                    "description": "Moving capitalised interest to internal contra",
                },
                "asset": DEFAULT_ASSET,
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in new_postings]

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=[
                "MOVE_CAPITALISED_INTEREST_TO_INTERNAL_CONTRA_MOCK_HOOK_GBP_CUSTOMER"
            ],
            effective_date=DEFAULT_DATE,
        )

    def test_post_posting_code_rollover_principal_and_interest_amount_checks_rollover_type(
        self,
    ):
        """
        Testing whether we consdier the auto_rollover_type when determining the adjustment amount
        as if auto_rollover_type == principal_and_interest, then we know balance is in the process
        of being updated to 0, but the async call may be out of step with the post_posting hook.
        """
        balances_ts = self.account_balances(
            default_committed=Decimal("200.08"), capitalised_interest=Decimal("0.8")
        )
        mock_vault = self.create_mock(balance_ts=balances_ts)

        postings = [
            self.outbound_transfer(amount=Decimal("200.08")),
        ]
        pib = self.mock_posting_instruction_batch(
            posting_instructions=postings,
            batch_details={"auto_rollover_type": "principal_and_interest"},
        )

        self.run_function(
            "post_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        new_postings = [
            {
                "amount": Decimal("0.8"),
                "denomination": DEFAULT_DENOMINATION,
                "client_transaction_id": "MOVE_CAPITALISED_INTEREST_TO_INTERNAL_CONTRA_"
                + "MOCK_HOOK_GBP_CUSTOMER",
                "from_account_id": "Main account",
                "from_account_address": CAPITALISED_INTEREST,
                "to_account_id": "Main account",
                "to_account_address": INTERNAL_CONTRA,
                "instruction_details": {
                    "description": "Moving capitalised interest to internal contra",
                },
                "asset": DEFAULT_ASSET,
            },
        ]

        expected_postings = [call(**kwargs) for kwargs in new_postings]

        mock_vault.make_internal_transfer_instructions.assert_has_calls(expected_postings)

        mock_vault.instruct_posting_batch.assert_called_with(
            posting_instructions=[
                "MOVE_CAPITALISED_INTEREST_TO_INTERNAL_CONTRA_MOCK_HOOK_GBP_CUSTOMER"
            ],
            effective_date=DEFAULT_DATE,
        )

    def test_post_parameter_change_code_monthly_after_application(self):
        mock_vault = self.create_mock(
            interest_application_frequency=UnionItemValue(key="monthly"),
            interest_application_hour=23,
            interest_application_minute=34,
            interest_application_second=45,
            APPLY_ACCRUED_INTEREST=datetime(2020, 1, 20),
        )

        old_parameters = {"interest_application_day": 20}
        new_parameters = {"interest_application_day": 10}

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters=old_parameters,
            new_parameters=new_parameters,
            effective_date=datetime(2020, 1, 25),
        )

        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule={
                "year": "2020",
                "month": "2",
                "day": "10",
                "hour": "23",
                "minute": "34",
                "second": "45",
            },
        )

    def test_post_parameter_change_code_quarterly_change_to_after_effective_date(self):
        mock_vault = self.create_mock(
            interest_application_frequency=UnionItemValue(key="quarterly"),
            interest_application_hour=23,
            interest_application_minute=34,
            interest_application_second=45,
            APPLY_ACCRUED_INTEREST=datetime(2020, 1, 10),
        )

        old_parameters = {"interest_application_day": 10}
        new_parameters = {"interest_application_day": 20}

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters=old_parameters,
            new_parameters=new_parameters,
            effective_date=datetime(2020, 4, 15),
        )

        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule={
                "year": "2020",
                "month": "4",
                "day": "20",
                "hour": "23",
                "minute": "34",
                "second": "45",
            },
        )

    def test_post_parameter_change_code_quarterly_change_to_before_effective_date(self):
        mock_vault = self.create_mock(
            interest_application_frequency=UnionItemValue(key="quarterly"),
            interest_application_hour=23,
            interest_application_minute=34,
            interest_application_second=45,
            APPLY_ACCRUED_INTEREST=datetime(2020, 1, 20),
        )

        old_parameters = {"interest_application_day": 20}
        new_parameters = {"interest_application_day": 10}

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters=old_parameters,
            new_parameters=new_parameters,
            effective_date=datetime(2020, 4, 15),
        )

        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule={
                "year": "2020",
                "month": "7",
                "day": "10",
                "hour": "23",
                "minute": "34",
                "second": "45",
            },
        )

    def test_post_parameter_change_code_annually_change_to_after_effective_date(self):
        mock_vault = self.create_mock(
            interest_application_frequency=UnionItemValue(key="annually"),
            interest_application_hour=23,
            interest_application_minute=34,
            interest_application_second=45,
            APPLY_ACCRUED_INTEREST=datetime(2020, 1, 10),
        )

        old_parameters = {"interest_application_day": 10}
        new_parameters = {"interest_application_day": 20}

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters=old_parameters,
            new_parameters=new_parameters,
            effective_date=datetime(2021, 1, 15),
        )

        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule={
                "year": "2021",
                "month": "1",
                "day": "20",
                "hour": "23",
                "minute": "34",
                "second": "45",
            },
        )

    def test_post_parameter_change_code_annually_change_to_before_effective_date(self):
        mock_vault = self.create_mock(
            interest_application_frequency=UnionItemValue(key="annually"),
            interest_application_hour=23,
            interest_application_minute=34,
            interest_application_second=45,
            APPLY_ACCRUED_INTEREST=datetime(2020, 1, 20),
        )

        old_parameters = {"interest_application_day": 20}
        new_parameters = {"interest_application_day": 10}

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters=old_parameters,
            new_parameters=new_parameters,
            effective_date=datetime(2021, 1, 15),
        )

        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule={
                "year": "2022",
                "month": "1",
                "day": "10",
                "hour": "23",
                "minute": "34",
                "second": "45",
            },
        )

    def test_apply_accrued_interest_zero_accrued_no_postings(self):
        balances_ts = self.account_balances(accrued_incoming=Decimal("0"))
        mock_vault = self.create_mock(
            balance_ts=balances_ts,
            fulfillment_precision=2,
            interest_application_frequency=UnionItemValue(key="monthly"),
            interest_application_day=1,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        self.run_function(
            "_apply_accrued_interest",
            mock_vault,
            vault=mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            denomination=DEFAULT_DENOMINATION,
            effective_date=datetime(2020, 1, 1),
            start_workflow=True,
        )

        mock_vault.make_internal_transfer_instructions.assert_not_called()
        mock_vault.instruct_posting_batch.assert_not_called()
        mock_vault.start_workflow.assert_not_called()
        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule={
                "year": "2020",
                "month": "2",
                "day": "1",
                "hour": "23",
                "minute": "59",
                "second": "59",
            },
        )

    def test_apply_accrued_interest_schedule_not_amended_with_arg_false(self):
        balances_ts = self.account_balances(accrued_incoming=Decimal("0"))
        mock_vault = self.create_mock(
            balance_ts=balances_ts,
            fulfillment_precision=2,
            interest_application_frequency=UnionItemValue(key="monthly"),
            interest_application_day=1,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        self.run_function(
            "_apply_accrued_interest",
            mock_vault,
            vault=mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            denomination=DEFAULT_DENOMINATION,
            effective_date=DEFAULT_DATE,
            amend_schedule=False,
        )

        mock_vault.amend_schedule.assert_not_called()

    def test_apply_accrued_interest_workflow_not_started_with_arg_false(self):
        balances_ts = self.account_balances(accrued_incoming=Decimal("1"))
        mock_vault = self.create_mock(
            balance_ts=balances_ts,
            fulfillment_precision=2,
            interest_application_frequency=UnionItemValue(key="monthly"),
            interest_application_day=1,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        self.run_function(
            "_apply_accrued_interest",
            mock_vault,
            vault=mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            denomination=DEFAULT_DENOMINATION,
            effective_date=datetime(2020, 1, 1),
            start_workflow=False,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("1.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=ACCRUED_INTEREST_PAYABLE,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_INTEREST_"
                    f"PAYABLE_COMMERCIAL_BANK_MONEY_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("1.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_INTEREST_"
                    f"PAYABLE_COMMERCIAL_BANK_MONEY_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("1.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=CAPITALISED_INTEREST,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"APPLY_ACCRUED_INTEREST_TO_CAPITALISED_MOCK_HOOK_"
                    f"{DEFAULT_DENOMINATION}_CUSTOMER",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                ),
            ]
        )

        mock_vault.start_workflow.assert_not_called()
        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule={
                "year": "2020",
                "month": "2",
                "day": "1",
                "hour": "23",
                "minute": "59",
                "second": "59",
            },
        )

    def test_apply_accrued_interest_positive_remainder(self):
        balances_ts = self.account_balances(accrued_incoming=Decimal("1.0005"))
        mock_vault = self.create_mock(
            balance_ts=balances_ts,
            fulfillment_precision=2,
            interest_application_frequency=UnionItemValue(key="monthly"),
            interest_application_day=1,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        self.run_function(
            "_apply_accrued_interest",
            mock_vault,
            vault=mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            denomination=DEFAULT_DENOMINATION,
            effective_date=datetime(2020, 1, 1),
            start_workflow=False,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("1.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=ACCRUED_INTEREST_PAYABLE,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_INTEREST_"
                    f"PAYABLE_COMMERCIAL_BANK_MONEY_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("1.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_INTEREST_"
                    f"PAYABLE_COMMERCIAL_BANK_MONEY_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("0.0005"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=ACCRUED_INTEREST_PAYABLE,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"REVERSE_ACCRUED_INTEREST_CUSTOMER_MOCK_HOOK_"
                    f"ACCRUED_INTEREST_PAYABLE_COMMERCIAL_BANK_MONEY_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("0.0005"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTEREST_PAID_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"REVERSE_ACCRUED_INTEREST_GL_MOCK_HOOK_"
                    f"ACCRUED_INTEREST_PAYABLE_COMMERCIAL_BANK_MONEY_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("1.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=CAPITALISED_INTEREST,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"APPLY_ACCRUED_INTEREST_TO_CAPITALISED_MOCK_HOOK_"
                    f"{DEFAULT_DENOMINATION}_CUSTOMER",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                ),
            ]
        )
        mock_vault.start_workflow.assert_not_called()
        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule={
                "year": "2020",
                "month": "2",
                "day": "1",
                "hour": "23",
                "minute": "59",
                "second": "59",
            },
        )

    def test_apply_accrued_interest_negative_remainder(self):
        balances_ts = self.account_balances(accrued_incoming=Decimal("1.0999"))
        mock_vault = self.create_mock(
            balance_ts=balances_ts,
            fulfillment_precision=2,
            interest_application_frequency=UnionItemValue(key="monthly"),
            interest_application_day=1,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        self.run_function(
            "_apply_accrued_interest",
            mock_vault,
            vault=mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            denomination=DEFAULT_DENOMINATION,
            effective_date=datetime(2020, 1, 1),
            start_workflow=False,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("1.10"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=ACCRUED_INTEREST_PAYABLE,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    client_transaction_id="APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_INTEREST_"
                    f"PAYABLE_COMMERCIAL_BANK_MONEY_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("1.10"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_INTEREST_"
                    f"PAYABLE_COMMERCIAL_BANK_MONEY_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("0.0001"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=ACCRUED_INTEREST_PAYABLE,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"ACCRUE_INTEREST_CUSTOMER_MOCK_HOOK_"
                    f"ACCRUED_INTEREST_PAYABLE_COMMERCIAL_BANK_MONEY_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("0.0001"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=INTEREST_PAID_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"ACCRUE_INTEREST_GL_MOCK_HOOK_"
                    f"ACCRUED_INTEREST_PAYABLE_COMMERCIAL_BANK_MONEY_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Zero out remainder after accrued interest applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("1.10"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=CAPITALISED_INTEREST,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"APPLY_ACCRUED_INTEREST_TO_CAPITALISED_MOCK_HOOK_"
                    f"{DEFAULT_DENOMINATION}_CUSTOMER",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                ),
            ]
        )
        mock_vault.start_workflow.assert_not_called()
        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule={
                "year": "2020",
                "month": "2",
                "day": "1",
                "hour": "23",
                "minute": "59",
                "second": "59",
            },
        )

    def test_apply_accrued_interest_workflow_started_with_arg_true(self):
        balances_ts = self.account_balances(accrued_incoming=Decimal(1))
        mock_vault = self.create_mock(
            balance_ts=balances_ts,
            fulfillment_precision=2,
            interest_application_frequency=UnionItemValue(key="monthly"),
            interest_application_day=1,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        self.run_function(
            "_apply_accrued_interest",
            mock_vault,
            vault=mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            denomination=DEFAULT_DENOMINATION,
            effective_date=datetime(2020, 1, 1),
            start_workflow=True,
        )

        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("1.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=ACCRUED_INTEREST_PAYABLE,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=INTERNAL_CONTRA,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"APPLY_INTEREST_CUSTOMER_MOCK_HOOK_ACCRUED_INTEREST_"
                    f"PAYABLE_COMMERCIAL_BANK_MONEY_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("1.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=ACCRUED_INTEREST_PAYABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"APPLY_INTEREST_GL_MOCK_HOOK_ACCRUED_INTEREST_"
                    f"PAYABLE_COMMERCIAL_BANK_MONEY_{DEFAULT_DENOMINATION}",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal("1.00"),
                    denomination=DEFAULT_DENOMINATION,
                    from_account_id=VAULT_ACCOUNT_ID,
                    from_account_address=INTERNAL_CONTRA,
                    to_account_id=VAULT_ACCOUNT_ID,
                    to_account_address=CAPITALISED_INTEREST,
                    asset=DEFAULT_ASSET,
                    client_transaction_id=f"APPLY_ACCRUED_INTEREST_TO_CAPITALISED_MOCK_HOOK_"
                    f"{DEFAULT_DENOMINATION}_CUSTOMER",
                    instruction_details={
                        "description": "Interest Applied.",
                        "event": "APPLY_ACCRUED_INTEREST",
                    },
                ),
            ]
        )
        mock_vault.start_workflow.assert_called_with(
            workflow="TIME_DEPOSIT_APPLIED_INTEREST_TRANSFER",
            context={"account_id": VAULT_ACCOUNT_ID, "applied_interest_amount": "1.00"},
        )
        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule={
                "year": "2020",
                "month": "2",
                "day": "1",
                "hour": "23",
                "minute": "59",
                "second": "59",
            },
        )

    def test_get_deposit_period_end_date_same_month(self):
        mock_vault = self.create_mock()

        deposit_period_end_date = self.run_function(
            "_get_period_end_date",
            mock_vault,
            account_creation_date=datetime(2019, 1, 1),
            delta_days=5,
            period_end_hour=21,
        )

        self.assertEqual(deposit_period_end_date, datetime(2019, 1, 6, 21, 0, 0))

    def test_get_period_end_date_next_month(self):
        mock_vault = self.create_mock()

        delta_days_end_date = self.run_function(
            "_get_period_end_date",
            mock_vault,
            account_creation_date=datetime(2019, 1, 1),
            period_end_hour=21,
            delta_days=31,
        )

        self.assertEqual(delta_days_end_date, datetime(2019, 2, 1, 21, 0, 0))

    def test_get_next_schedule_date_same_day_monthly(self):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2019, 1, 1),
            schedule_frequency="monthly",
            intended_day=1,
        )

        self.assertEqual(next_schedule_date, datetime(2019, 2, 1))

    def test_get_next_schedule_date_day_exists_in_target_month_monthly(self):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2019, 1, 1),
            schedule_frequency="monthly",
            intended_day=5,
        )

        self.assertEqual(next_schedule_date, datetime(2019, 1, 5))

    def test_get_next_schedule_date_day_exists_in_target_month_quarterly(self):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2019, 1, 1),
            schedule_frequency="quarterly",
            intended_day=5,
        )

        self.assertEqual(next_schedule_date, datetime(2019, 4, 5))

    def test_get_next_schedule_date_day_exists_in_target_month_annually(self):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2019, 1, 1),
            schedule_frequency="annually",
            intended_day=5,
        )

        self.assertEqual(next_schedule_date, datetime(2020, 1, 5))

    def test_get_next_schedule_date_day_exists_in_target_month_semi_annually(self):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2019, 1, 1),
            schedule_frequency="semi_annually",
            intended_day=5,
        )

        self.assertEqual(next_schedule_date, datetime(2019, 7, 5))

    def test_get_next_schedule_date_day_doesnt_exist_in_target_month_monthly(self):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2019, 1, 1),
            schedule_frequency="monthly",
            intended_day=29,
        )

        self.assertEqual(next_schedule_date, datetime(2019, 1, 29))

    def test_get_next_schedule_date_day_doesnt_exist_in_target_month_quarterly(self):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2019, 1, 1),
            schedule_frequency="quarterly",
            intended_day=31,
        )

        self.assertEqual(next_schedule_date, datetime(2019, 4, 30))

    def test_get_next_schedule_date_day_doesnt_exist_in_target_month_annually(self):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2020, 2, 1),
            schedule_frequency="annually",
            intended_day=29,
        )

        self.assertEqual(next_schedule_date, datetime(2021, 2, 28))

    def test_get_next_schedule_date_day_doesnt_exist_in_target_month_semi_annually(
        self,
    ):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2019, 3, 1),
            schedule_frequency="semi_annually",
            intended_day=31,
        )

        self.assertEqual(next_schedule_date, datetime(2019, 9, 30))

    def test_get_next_schedule_date_weekly(self):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2019, 3, 1),
            schedule_frequency="weekly",
            intended_day=31,
        )

        self.assertEqual(next_schedule_date, datetime(2019, 3, 8))

    def test_get_next_schedule_date_fortnightly(self):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2019, 3, 1),
            schedule_frequency="fortnightly",
            intended_day=1,
        )

        self.assertEqual(next_schedule_date, datetime(2019, 3, 15))

    def test_get_next_schedule_date_four_weekly(self):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2019, 3, 1),
            schedule_frequency="four_weekly",
            intended_day=1,
        )

        self.assertEqual(next_schedule_date, datetime(2019, 3, 29))

    def test_get_next_schedule_date_four_weekly_end_of_month_no_application_date(self):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2019, 3, 31),
            schedule_frequency="four_weekly",
            intended_day=1,
        )

        self.assertEqual(next_schedule_date, datetime(2019, 4, 28))

    def test_get_next_schedule_date_fortnightly_leap_year_no_application_date(self):
        mock_vault = self.create_mock()

        next_schedule_date = self.run_function(
            "_get_next_schedule_date",
            mock_vault,
            start_date=datetime(2020, 2, 15),
            schedule_frequency="fortnightly",
            intended_day=1,
        )

        self.assertEqual(next_schedule_date, datetime(2020, 2, 29))

    def test_get_apply_accrued_interest_date_monthly_same_month(self):
        mock_vault = self.create_mock(
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            interest_application_frequency="monthly",
            interest_application_day=3,
            effective_date=datetime(2019, 1, 1),
        )

        self.assertEqual(apply_accrued_interest_date, datetime(2019, 1, 3, 23, 59, 59))

    def test_get_apply_accrued_interest_date_monthly_next_month(self):
        mock_vault = self.create_mock(
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            interest_application_frequency="monthly",
            interest_application_day=3,
            effective_date=datetime(2019, 1, 5),
        )

        self.assertEqual(apply_accrued_interest_date, datetime(2019, 2, 3, 23, 59, 59))

    def test_get_apply_accrued_interest_date_quarterly_day_after_effective_date(self):
        mock_vault = self.create_mock(
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            interest_application_frequency="quarterly",
            interest_application_day=3,
            effective_date=datetime(2019, 1, 2),
        )

        self.assertEqual(apply_accrued_interest_date, datetime(2019, 4, 3, 23, 59, 59))

    def test_get_apply_accrued_interest_date_quarterly_day_before_effective_date(self):
        mock_vault = self.create_mock(
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            interest_application_frequency="quarterly",
            interest_application_day=3,
            effective_date=datetime(2019, 1, 5),
        )

        self.assertEqual(apply_accrued_interest_date, datetime(2019, 4, 3, 23, 59, 59))

    def test_get_apply_accrued_interest_date_semi_annually_day_after_effective_date(
        self,
    ):
        mock_vault = self.create_mock(
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            interest_application_frequency="semi_annually",
            interest_application_day=3,
            effective_date=datetime(2019, 1, 2),
        )

        self.assertEqual(apply_accrued_interest_date, datetime(2019, 7, 3, 23, 59, 59))

    def test_get_apply_accrued_interest_date_semi_annually_day_before_effective_date(
        self,
    ):
        mock_vault = self.create_mock(
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            interest_application_frequency="semi_annually",
            interest_application_day=3,
            effective_date=datetime(2019, 1, 5),
        )

        self.assertEqual(apply_accrued_interest_date, datetime(2019, 7, 3, 23, 59, 59))

    def test_get_apply_accrued_interest_date_annually_day_after_effective_date(self):
        mock_vault = self.create_mock(
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            interest_application_frequency="annually",
            interest_application_day=3,
            effective_date=datetime(2019, 1, 2),
        )

        self.assertEqual(apply_accrued_interest_date, datetime(2020, 1, 3, 23, 59, 59))

    def test_get_apply_accrued_interest_date_annually_day_before_effective_date(self):
        mock_vault = self.create_mock(
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_accrued_interest_date = self.run_function(
            "_get_apply_accrued_interest_date",
            mock_vault,
            vault=mock_vault,
            interest_application_frequency="annually",
            interest_application_day=3,
            effective_date=datetime(2019, 1, 5),
        )

        self.assertEqual(apply_accrued_interest_date, datetime(2020, 1, 3, 23, 59, 59))

    def test_get_apply_accrued_interest_schedule(self):
        mock_vault = self.create_mock(
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        apply_interest_schedule = self.run_function(
            "_get_apply_accrued_interest_schedule",
            mock_vault,
            vault=mock_vault,
            interest_application_frequency="monthly",
            interest_application_day=3,
            effective_date=datetime(2019, 1, 1),
        )

        expected_apply_interest_schedule = {
            "year": "2019",
            "month": "1",
            "day": "3",
            "hour": "23",
            "minute": "59",
            "second": "59",
        }
        self.assertEqual(apply_interest_schedule, expected_apply_interest_schedule)

    def test_get_accrue_interest_schedule(self):
        mock_vault = self.create_mock(
            interest_accrual_hour=23,
            interest_accrual_minute=58,
            interest_accrual_second=59,
        )

        accrue_interest_schedule = self.run_function(
            "_get_accrue_interest_schedule", mock_vault, vault=mock_vault
        )

        expected_accrue_interest_schedule = {
            "hour": "23",
            "minute": "58",
            "second": "59",
        }
        self.assertEqual(accrue_interest_schedule, expected_accrue_interest_schedule)

    def test_get_account_close_schedule(self):
        mock_vault = self.create_mock()

        account_close_schedule = self.run_function(
            "_get_account_close_schedule",
            mock_vault,
            vault=mock_vault,
            account_creation_date=datetime(2020, 1, 1),
            delta_days=5,
            period_end_hour=15,
            account_closure_period=2,
        )

        expected_account_close_schedule = {
            "year": "2020",
            "month": "1",
            "day": "8",
            "hour": "15",
            "minute": "0",
            "second": "0",
        }

        self.assertEqual(account_close_schedule, expected_account_close_schedule)

    def test_get_account_maturity_schedule_one_month(self):
        mock_vault = self.create_mock()

        account_maturity_schedule = self.run_function(
            "_get_account_maturity_schedule",
            mock_vault,
            vault=mock_vault,
            term_unit="months",
            term=1,
            account_creation_date=datetime(2020, 1, 1, 2, 3, 5),
            calendar_events=None,
        )

        expected_account_maturity_schedule = {
            "year": "2020",
            "month": "2",
            "day": "1",
            "hour": "2",
            "minute": "3",
            "second": "5",
        }

        self.assertEqual(account_maturity_schedule, expected_account_maturity_schedule)

    def test_get_account_maturity_schedule_one_leap_year(self):
        mock_vault = self.create_mock()

        account_maturity_schedule = self.run_function(
            "_get_account_maturity_schedule",
            mock_vault,
            vault=mock_vault,
            term_unit="months",
            term=12,
            account_creation_date=datetime(2020, 1, 1, 2, 3, 5),
            calendar_events=None,
        )

        expected_account_maturity_schedule = {
            "year": "2021",
            "month": "1",
            "day": "1",
            "hour": "2",
            "minute": "3",
            "second": "5",
        }

        self.assertEqual(account_maturity_schedule, expected_account_maturity_schedule)

    def test_get_account_maturity_schedule_one_month_last_day_of_month(self):
        mock_vault = self.create_mock()

        account_maturity_schedule = self.run_function(
            "_get_account_maturity_schedule",
            mock_vault,
            vault=mock_vault,
            term_unit="months",
            term=1,
            account_creation_date=datetime(2020, 1, 31, 2, 3, 5),
            calendar_events=None,
        )

        expected_account_maturity_schedule = {
            "year": "2020",
            "month": "2",
            "day": "29",
            "hour": "2",
            "minute": "3",
            "second": "5",
        }

        self.assertEqual(account_maturity_schedule, expected_account_maturity_schedule)

    def test_get_account_maturity_schedule_seven_days(self):
        mock_vault = self.create_mock()

        account_maturity_schedule = self.run_function(
            "_get_account_maturity_schedule",
            mock_vault,
            vault=mock_vault,
            term_unit="days",
            term=7,
            account_creation_date=datetime(2020, 1, 1, 2, 3, 5),
            calendar_events=None,
        )

        expected_account_maturity_schedule = {
            "year": "2020",
            "month": "1",
            "day": "8",
            "hour": "2",
            "minute": "3",
            "second": "5",
        }

        self.assertEqual(account_maturity_schedule, expected_account_maturity_schedule)

    def test_get_account_maturity_date_one_month(self):
        mock_vault = self.create_mock()

        account_maturity_date = self.run_function(
            "_get_account_maturity_date",
            mock_vault,
            term_unit="months",
            term=1,
            account_creation_date=datetime(2020, 1, 1, 2, 3, 5),
            calendar_events=None,
        )

        self.assertEqual(account_maturity_date, datetime(2020, 2, 1, 2, 3, 5))

    def test_get_account_maturity_date_one_leap_year(self):
        mock_vault = self.create_mock()

        account_maturity_date = self.run_function(
            "_get_account_maturity_date",
            mock_vault,
            term_unit="months",
            term=12,
            account_creation_date=datetime(2020, 1, 1, 2, 3, 5),
            calendar_events=None,
        )

        self.assertEqual(account_maturity_date, datetime(2021, 1, 1, 2, 3, 5))

    def test_get_account_maturity_date_one_month_last_day_of_month(self):
        mock_vault = self.create_mock()

        account_maturity_date = self.run_function(
            "_get_account_maturity_date",
            mock_vault,
            term_unit="months",
            term=1,
            account_creation_date=datetime(2020, 1, 31, 2, 3, 5),
            calendar_events=None,
        )

        self.assertEqual(account_maturity_date, datetime(2020, 2, 29, 2, 3, 5))

    def test_get_account_maturity_date_seven_days(self):
        mock_vault = self.create_mock()

        account_maturity_date = self.run_function(
            "_get_account_maturity_date",
            mock_vault,
            term_unit="days",
            term=7,
            account_creation_date=datetime(2020, 1, 1, 2, 3, 5),
            calendar_events=None,
        )

        self.assertEqual(account_maturity_date, datetime(2020, 1, 8, 2, 3, 5))

    def test_do_account_maturity_amends_schedule(self):
        balances_ts = self.account_balances()
        mock_vault = self.create_mock(
            balance_ts=balances_ts,
            fulfillment_precision=2,
            interest_application_frequency=UnionItemValue(key="monthly"),
            interest_application_day=1,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        self.run_function(
            "_initiate_account_maturity_process",
            mock_vault,
            vault=mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            denomination=DEFAULT_DENOMINATION,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.amend_schedule.assert_has_calls(
            [
                call(
                    event_type="ACCRUE_INTEREST",
                    new_schedule={
                        "year": "1971",
                        "start_date": "1970-01-01",
                        "end_date": "1970-01-01",
                    },
                ),
                call(
                    event_type="APPLY_ACCRUED_INTEREST",
                    new_schedule={
                        "year": "1971",
                        "start_date": "1970-01-01",
                        "end_date": "1970-01-01",
                    },
                ),
            ]
        )

    def test_do_account_maturity_starts_maturity_workflow(self):
        balances_ts = self.account_balances()
        mock_vault = self.create_mock(
            balance_ts=balances_ts,
            fulfillment_precision=2,
            interest_application_frequency=UnionItemValue(key="monthly"),
            interest_application_day=1,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        self.run_function(
            "_initiate_account_maturity_process",
            mock_vault,
            vault=mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            denomination=DEFAULT_DENOMINATION,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.start_workflow.assert_called_with(
            workflow="TIME_DEPOSIT_MATURITY",
            context={
                "account_id": mock_vault.account_id,
                "applied_interest_amount": "0.00",
            },
        )

    def test_do_account_maturity_starts_maturity_workflow_applied_interest(self):
        balances_ts = self.account_balances(accrued_incoming=Decimal("12.34"))
        mock_vault = self.create_mock(
            balance_ts=balances_ts,
            fulfillment_precision=2,
            interest_application_frequency=UnionItemValue(key="monthly"),
            interest_application_day=1,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        self.run_function(
            "_initiate_account_maturity_process",
            mock_vault,
            vault=mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            denomination=DEFAULT_DENOMINATION,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.start_workflow.assert_called_with(
            workflow="TIME_DEPOSIT_MATURITY",
            context={
                "account_id": mock_vault.account_id,
                "applied_interest_amount": "12.34",
            },
        )
        self.assertEqual(mock_vault.start_workflow.call_count, 1)

    def test_do_account_maturity_starts_maturity_workflow_applied_interest_rounded(
        self,
    ):
        balances_ts = self.account_balances(accrued_incoming=Decimal("12.34123"))
        mock_vault = self.create_mock(
            balance_ts=balances_ts,
            fulfillment_precision=2,
            interest_application_frequency=UnionItemValue(key="monthly"),
            interest_application_day=1,
            interest_application_hour=23,
            interest_application_minute=59,
            interest_application_second=59,
        )

        self.run_function(
            "_initiate_account_maturity_process",
            mock_vault,
            vault=mock_vault,
            event_type="APPLY_ACCRUED_INTEREST",
            denomination=DEFAULT_DENOMINATION,
            effective_date=DEFAULT_DATE,
        )

        mock_vault.start_workflow.assert_called_with(
            workflow="TIME_DEPOSIT_MATURITY",
            context={
                "account_id": mock_vault.account_id,
                "applied_interest_amount": "12.34",
            },
        )

    def test_check_account_closure_period_end_calls_workflow_with_zero_balance(self):
        balances_ts = self.account_balances()
        mock_vault = self.create_mock(balance_ts=balances_ts)

        self.run_function(
            "_check_account_closure_period_end",
            mock_vault,
            vault=mock_vault,
            denomination=DEFAULT_DENOMINATION,
        )

        mock_vault.start_workflow.assert_called_with(
            workflow="TIME_DEPOSIT_CLOSURE",
            context={"account_id": mock_vault.account_id},
        )

    def test_check_account_closure_period_end_doesnt_call_workflow_with_committed_balance(
        self,
    ):
        balances_ts = self.account_balances(default_committed=Decimal(1))
        mock_vault = self.create_mock(balance_ts=balances_ts)

        self.run_function(
            "_check_account_closure_period_end",
            mock_vault,
            vault=mock_vault,
            denomination=DEFAULT_DENOMINATION,
        )

        mock_vault.start_workflow.assert_not_called()

    def test_check_account_closure_period_end_doesnt_call_workflow_with_pending_inbound_balance(
        self,
    ):
        balances_ts = self.account_balances(default_pending_incoming=Decimal(1))
        mock_vault = self.create_mock(balance_ts=balances_ts)

        self.run_function(
            "_check_account_closure_period_end",
            mock_vault,
            vault=mock_vault,
            denomination=DEFAULT_DENOMINATION,
        )

        mock_vault.start_workflow.assert_not_called()

    def test_get_available_balance_gets_pending_in(self):
        balances_ts = self.account_balances(default_pending_incoming=Decimal(1))
        mock_vault = self.create_mock(balance_ts=balances_ts)

        available_balance = self.run_function(
            "_get_available_balance",
            mock_vault,
            vault=mock_vault,
            balance_address=DEFAULT_ADDRESS,
            phases_to_include=[Phase.PENDING_IN],
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(available_balance, Decimal(1))

    def test_get_available_balance_gets_pending_in_and_committed(self):
        balances_ts = self.account_balances(
            default_committed=Decimal(2), default_pending_incoming=Decimal(1)
        )
        mock_vault = self.create_mock(balance_ts=balances_ts)

        available_balance = self.run_function(
            "_get_available_balance",
            mock_vault,
            vault=mock_vault,
            balance_address=DEFAULT_ADDRESS,
            phases_to_include=[Phase.PENDING_IN, Phase.COMMITTED],
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(available_balance, Decimal(3))

    def test_get_available_balance_gets_committed_and_pending_out(self):
        balances_ts = self.account_balances(
            default_committed=Decimal(2), default_pending_outgoing=Decimal(-5)
        )
        mock_vault = self.create_mock(balance_ts=balances_ts)

        available_balance = self.run_function(
            "_get_available_balance",
            mock_vault,
            vault=mock_vault,
            balance_address=DEFAULT_ADDRESS,
            phases_to_include=[Phase.PENDING_OUT, Phase.COMMITTED],
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(available_balance, Decimal(-3))

    def test_get_available_balance_ignores_not_included_phases(self):
        balances_ts = self.account_balances(
            default_committed=Decimal(2),
            default_pending_outgoing=Decimal(-5),
            default_pending_incoming=Decimal(300),
        )
        mock_vault = self.create_mock(balance_ts=balances_ts)

        available_balance = self.run_function(
            "_get_available_balance",
            mock_vault,
            vault=mock_vault,
            balance_address=DEFAULT_ADDRESS,
            phases_to_include=[Phase.PENDING_OUT, Phase.COMMITTED],
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(available_balance, Decimal(-3))

    def test_post_parameter_change_code_semi_annually_change_to_after_effective_date(
        self,
    ):
        mock_vault = self.create_mock(
            interest_application_frequency=UnionItemValue(key="semi_annually"),
            interest_application_hour=23,
            interest_application_minute=34,
            interest_application_second=45,
            APPLY_ACCRUED_INTEREST=datetime(2020, 1, 20),
        )

        old_parameters = {"interest_application_day": 10}
        new_parameters = {"interest_application_day": 20}

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters=old_parameters,
            new_parameters=new_parameters,
            effective_date=datetime(2020, 7, 21),
        )

        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule={
                "year": "2021",
                "month": "1",
                "day": "20",
                "hour": "23",
                "minute": "34",
                "second": "45",
            },
        )

    def test_post_parameter_change_code_semi_annually_change_to_before_effective_date(
        self,
    ):
        mock_vault = self.create_mock(
            interest_application_frequency=UnionItemValue(key="semi_annually"),
            interest_application_hour=23,
            interest_application_minute=34,
            interest_application_second=45,
            APPLY_ACCRUED_INTEREST=datetime(2020, 1, 20),
        )

        old_parameters = {"interest_application_day": 20}
        new_parameters = {"interest_application_day": 10}

        self.run_function(
            "post_parameter_change_code",
            mock_vault,
            old_parameters=old_parameters,
            new_parameters=new_parameters,
            effective_date=datetime(2020, 4, 15),
        )

        mock_vault.amend_schedule.assert_called_with(
            event_type="APPLY_ACCRUED_INTEREST",
            new_schedule={
                "year": "2020",
                "month": "7",
                "day": "10",
                "hour": "23",
                "minute": "34",
                "second": "45",
            },
        )

    def test_get_account_maturity_date_with_events_seven_days(self):
        mock_vault = self.create_mock()

        account_maturity_date = self.run_function(
            "_get_account_maturity_date",
            mock_vault,
            term_unit="days",
            term=7,
            account_creation_date=datetime(2020, 1, 1, 2, 3, 5),
            calendar_events=[
                CalendarEvent(
                    "NEW_YEAR",
                    TIME_DEPOSIT_BANK_HOLIDAY,
                    datetime(2020, 1, 8, 2, 3, 0),
                    datetime(2020, 1, 8, 2, 4, 0),
                )
            ],
        )

        self.assertEqual(account_maturity_date, datetime(2020, 1, 9, 2, 3, 5))

    def test_get_account_maturity_date_with_events_one_month_last_day_of_month(self):
        mock_vault = self.create_mock()

        account_maturity_date = self.run_function(
            "_get_account_maturity_date",
            mock_vault,
            term_unit="months",
            term=1,
            account_creation_date=datetime(2020, 1, 31, 2, 3, 5),
            calendar_events=[
                CalendarEvent(
                    "NEW_YEAR",
                    TIME_DEPOSIT_BANK_HOLIDAY,
                    datetime(2020, 2, 29, 2, 3, 0),
                    datetime(2020, 2, 29, 2, 4, 0),
                )
            ],
        )

        self.assertEqual(account_maturity_date, datetime(2020, 3, 1, 2, 3, 5))

    def test_get_account_maturity_date_with_events_one_month(self):
        mock_vault = self.create_mock()

        account_maturity_date = self.run_function(
            "_get_account_maturity_date",
            mock_vault,
            term_unit="months",
            term=1,
            account_creation_date=datetime(2020, 1, 1, 2, 3, 5),
            calendar_events=[
                CalendarEvent(
                    "NEW_YEAR",
                    TIME_DEPOSIT_BANK_HOLIDAY,
                    datetime(2020, 2, 1, 2, 3, 0),
                    datetime(2020, 2, 1, 2, 4, 0),
                )
            ],
        )

        self.assertEqual(account_maturity_date, datetime(2020, 2, 2, 2, 3, 5))

    def test_get_account_maturity_date_with_events_one_leap_year(self):
        mock_vault = self.create_mock()

        account_maturity_date = self.run_function(
            "_get_account_maturity_date",
            mock_vault,
            term_unit="months",
            term=12,
            account_creation_date=datetime(2020, 1, 1, 2, 3, 5),
            calendar_events=[
                CalendarEvent(
                    "NEW_YEAR",
                    TIME_DEPOSIT_BANK_HOLIDAY,
                    datetime(2021, 1, 1, 2, 3, 0),
                    datetime(2021, 1, 1, 2, 4, 0),
                )
            ],
        )

        self.assertEqual(account_maturity_date, datetime(2021, 1, 2, 2, 3, 5))

    def test_falls_on_calendar_events_true(self):
        mock_vault = self.create_mock()

        account_maturity_date = self.run_function(
            "_falls_on_calendar_events",
            mock_vault,
            effective_date=datetime(2021, 1, 1, 2, 3, 0),
            calendar_events=[
                CalendarEvent(
                    "NEW_YEAR",
                    TIME_DEPOSIT_BANK_HOLIDAY,
                    datetime(2021, 1, 1, 2, 3, 0),
                    datetime(2021, 1, 1, 2, 4, 0),
                )
            ],
        )

        self.assertEqual(account_maturity_date, True)

    def test_falls_on_calendar_events_false(self):
        mock_vault = self.create_mock()

        account_maturity_date = self.run_function(
            "_falls_on_calendar_events",
            mock_vault,
            effective_date=datetime(2021, 1, 2, 2, 3, 0),
            calendar_events=[
                CalendarEvent(
                    "NEW_YEAR",
                    TIME_DEPOSIT_BANK_HOLIDAY,
                    datetime(2021, 1, 1, 2, 3, 0),
                    datetime(2021, 1, 1, 2, 4, 0),
                )
            ],
        )

        self.assertEqual(account_maturity_date, False)

    def test_get_available_fee_free_limit(self):
        mock_vault = self.create_mock()

        available_fee_free_limit = self.run_function(
            "_get_available_fee_free_limit",
            mock_vault,
            latest_available_balance=Decimal("100"),
            fee_free_percentage_limit=Decimal("0.1"),
        )

        self.assertEqual(available_fee_free_limit, Decimal("10"))
