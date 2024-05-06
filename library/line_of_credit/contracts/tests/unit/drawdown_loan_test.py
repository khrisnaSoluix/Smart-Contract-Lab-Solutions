# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import call, patch, ANY

# common
from inception_sdk.vault.contracts.types_extension import (
    Balance,
    BalanceDefaultDict,
    Tside,
    Phase,
    Rejected,
    RejectedReason,
    DEFAULT_ASSET,
    DEFAULT_ADDRESS,
    Vault,
    PostingInstruction,
    PostingInstructionType,
)
from inception_sdk.test_framework.contracts.unit.common import (
    ContractTest,
    balance_dimensions,
)
from inception_sdk.test_framework.common.constants import DEFAULT_DENOMINATION

# Line of Credit constants
import library.line_of_credit.constants.accounts as accounts
import library.line_of_credit.constants.addresses as address


DEFAULT_DATE = datetime(2020, 1, 10)
DEFAULT_LINE_OF_CREDIT_ACCOUNT_ID = "Line of Credit Account"

# Debt Management Dimensions
DEFAULT_DIMENSIONS = balance_dimensions()
EMI_DIMENSIONS = balance_dimensions(address=address.EMI)
INTERNAL_CONTRA_DIMENSIONS = balance_dimensions(address=address.INTERNAL_CONTRA)
PRINCIPAL_DIMENSIONS = balance_dimensions(address=address.PRINCIPAL)
PRINCIPAL_DUE_DIMENSIONS = balance_dimensions(address=address.PRINCIPAL_DUE)
PRINCIPAL_OVERDUE_DIMENSIONS = balance_dimensions(address=address.PRINCIPAL_OVERDUE)
INTEREST_DIMENSIONS = balance_dimensions(address=address.ACCRUED_INTEREST_RECEIVABLE)
INTEREST_DUE_DIMENSIONS = balance_dimensions(address=address.INTEREST_DUE)
INTEREST_OVERDUE_DIMENSIONS = balance_dimensions(address=address.INTEREST_OVERDUE)


class DrawdownLoanTest(ContractTest):
    contract_file = "library/line_of_credit/contracts/template/drawdown_loan.py"
    side = Tside.ASSET
    default_denom = DEFAULT_DENOMINATION

    def create_mock(
        self,
        balance_ts=None,
        postings=None,
        creation_date=DEFAULT_DATE,
        denomination=DEFAULT_DENOMINATION,
        **kwargs,
    ):
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
            **kwargs,
        )

    def account_balances(
        self,
        dt: datetime = DEFAULT_DATE,
        default=Decimal("0"),
        principal=Decimal("0"),
        interest=Decimal("0"),
        emi=Decimal("0"),
        principal_due=Decimal("0"),
        interest_due=Decimal("0"),
        principal_overdue=Decimal("0"),
        interest_overdue=Decimal("0"),
        internal_contra=Decimal("0"),
    ) -> list[tuple[datetime, BalanceDefaultDict]]:

        # only use a small subset for simplicity's sake
        balance_default_dict = BalanceDefaultDict(
            lambda: Balance(net=Decimal("0")),
            {
                DEFAULT_DIMENSIONS: Balance(net=default),
                PRINCIPAL_DIMENSIONS: Balance(net=principal),
                PRINCIPAL_DUE_DIMENSIONS: Balance(net=principal_due),
                PRINCIPAL_OVERDUE_DIMENSIONS: Balance(net=principal_overdue),
                INTEREST_DIMENSIONS: Balance(net=interest),
                INTEREST_DUE_DIMENSIONS: Balance(net=interest_due),
                INTEREST_OVERDUE_DIMENSIONS: Balance(net=interest_overdue),
                EMI_DIMENSIONS: Balance(net=emi),
                INTERNAL_CONTRA_DIMENSIONS: Balance(net=internal_contra),
            },
        )
        return [(dt, balance_default_dict)]

    def expected_aggregate_postings(
        self,
        account_id: str,
        address: str,
        aggregate_prefix: str,
        amount: Decimal,
        credit_aggregate_address: bool = False,
    ) -> list[PostingInstruction]:

        instruction_details = {"description": "aggregate balances"}
        aggregate_address = f"{aggregate_prefix}_{address}"

        common_args = dict(
            account_id=account_id,
            amount=amount,
            client_transaction_id=f"AGGREGATE_{aggregate_address}_{self.hook_execution_id}",
            instruction_details=instruction_details,
            denomination=DEFAULT_DENOMINATION,
            instruction_type=PostingInstructionType.CUSTOM_INSTRUCTION,
            phase=Phase.COMMITTED,
            posting_id=None,
            override_all_restrictions=True,
            custom_instruction_grouping_key=ANY,
            client_id=None,
        )

        if credit_aggregate_address:
            return [
                self.mock_posting_instruction(
                    address="INTERNAL_CONTRA", credit=False, **common_args
                ),
                self.mock_posting_instruction(
                    address=aggregate_address, credit=True, **common_args
                ),
            ]
        else:
            return [
                self.mock_posting_instruction(
                    address=aggregate_address, credit=False, **common_args
                ),
                self.mock_posting_instruction(
                    address="INTERNAL_CONTRA", credit=True, **common_args
                ),
            ]


class PrePostingCodeTest(DrawdownLoanTest):
    def setUp(self):
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE,
        )
        self.mock_vault = self.create_mock(
            balance_ts=balance_ts,
        )
        self.test_postings = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.inbound_hard_settlement(denomination=DEFAULT_DENOMINATION, amount="200")
            ],
        )

    def test_regular_postings_are_rejected(self):

        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                self.mock_vault,
                postings=self.test_postings,
                effective_date=DEFAULT_DATE,
            )
        self.assertEqual(e.exception.reason_code, RejectedReason.CLIENT_CUSTOM_REASON)
        self.assertEqual(
            str(e.exception),
            "Reject all regular postings when unsupervised",
        )

    def test_pre_posting_allows_posting_with_override(self):

        pib = self.mock_posting_instruction_batch(
            posting_instructions=[self.test_postings],
            batch_details={"force_override": "true"},
        )

        self.run_function(
            "pre_posting_code",
            self.mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.assert_no_side_effects(self.mock_vault)


class PostActivationCodeTest(DrawdownLoanTest):
    @patch("library.features.lending.disbursement.get_posting_instructions")
    def test_disbursement(self, mocked_disbursement_posting):
        principal_amount = Decimal("100000")
        mock_vault = self.create_mock(
            principal=principal_amount,
            deposit_account=accounts.DEPOSIT_ACCOUNT,
            denomination=DEFAULT_DENOMINATION,
            line_of_credit_account_id=accounts.LOC_ACCOUNT,
            make_instructions_return_full_objects=True,
        )

        postings = [
            {
                "amount": Decimal("100000"),
                "denomination": DEFAULT_DENOMINATION,
                "client_transaction_id": "MOCK_HOOK_PRINCIPAL_DISBURSEMENT",
                "from_account_id": "Main account",
                "from_account_address": address.PRINCIPAL,
                "to_account_id": accounts.DEPOSIT_ACCOUNT,
                "to_account_address": DEFAULT_ADDRESS,
                "instruction_details": {
                    "description": "Principal disbursement of 100000",
                    "event": "PRINCIPAL_PAYMENT",
                },
                "asset": DEFAULT_ASSET,
            },
        ]

        expected_disbursement_postings = [call(**kwargs) for kwargs in postings]

        expected_loc_postings = [
            # total principal
            *self.expected_aggregate_postings(
                account_id=accounts.LOC_ACCOUNT,
                address=address.PRINCIPAL,
                aggregate_prefix="TOTAL",
                # sum of both principals
                amount=Decimal("100000"),
            ),
        ]

        def mock_disbursement_posting_instructions(
            vault: Vault, denomination: str, principal_address: str = address.PRINCIPAL
        ) -> list[PostingInstruction]:
            return vault.make_internal_transfer_instructions(
                amount=principal_amount,
                denomination=denomination,
                client_transaction_id=f"BATCH_\
                    {vault.get_hook_execution_id()}\
                        _PRINCIPAL_DISBURSEMENT",
                from_account_id=vault.account_id,
                from_account_address=address.PRINCIPAL,
                to_account_id=accounts.DEPOSIT_ACCOUNT,
                to_account_address=DEFAULT_ADDRESS,
                instruction_details={
                    "description": f"Principal disbursement of {principal_amount}",
                    "event": "PRINCIPAL_PAYMENT",
                },
                asset=DEFAULT_ASSET,
            )

        mocked_disbursement_posting.side_effect = mock_disbursement_posting_instructions

        self.run_function("post_activate_code", mock_vault)
        mock_vault.make_internal_transfer_instructions.assert_has_calls(
            expected_disbursement_postings
        )

        mock_vault.instruct_posting_batch.assert_has_calls(
            [
                call(
                    posting_instructions=ANY,  # this is asserted on above
                    effective_date=DEFAULT_DATE,
                    client_batch_id="BATCH_MOCK_HOOK_PRINCIPAL_DISBURSEMENT",
                ),
                call(
                    posting_instructions=expected_loc_postings,
                    effective_date=DEFAULT_DATE,
                    client_batch_id=f"AGGREGATE_LOC_{self.hook_execution_id}",
                    batch_details={"force_override": "true"},
                ),
            ]
        )
        self.assertEqual(mock_vault.instruct_posting_batch.call_count, 2)


class CloseCodeTest(DrawdownLoanTest):

    COMMON_POSTING_ARGS = dict(
        denomination=DrawdownLoanTest.default_denom,
        instruction_type=PostingInstructionType.CUSTOM_INSTRUCTION,
        phase=Phase.COMMITTED,
        posting_id=None,
        override_all_restrictions=True,
        custom_instruction_grouping_key=ANY,
        client_id=None,
    )

    def expected_clear_emi_postings(
        self,
        amount: Decimal,
    ) -> list[PostingInstruction]:
        instruction_details = {
            "description": "Clearing EMI address balance",
            "event": "END_OF_LOAN",
        }

        common_args = (
            dict(
                account_id="Main account",
                amount=amount,
                client_transaction_id=f"CLEAR_EMI_{self.hook_execution_id}",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )

        return [
            self.mock_posting_instruction(
                address=address.INTERNAL_CONTRA, credit=False, **common_args
            ),
            self.mock_posting_instruction(address=address.EMI, credit=True, **common_args),
        ]

    def expected_clear_emi_aggregate_postings(
        self,
        amount: Decimal,
    ) -> list[PostingInstruction]:
        instruction_details = {
            "description": "Removing EMI from aggregate balance",
            "event": "END_OF_LOAN",
        }

        common_args = (
            dict(
                account_id=DEFAULT_LINE_OF_CREDIT_ACCOUNT_ID,
                amount=amount,
                client_transaction_id=f"UPDATE_TOTAL_EMI_{self.hook_execution_id}",
                instruction_details=instruction_details,
            )
            | (self.COMMON_POSTING_ARGS)
        )

        return [
            self.mock_posting_instruction(
                address=address.INTERNAL_CONTRA, credit=False, **common_args
            ),
            self.mock_posting_instruction(
                address=f"TOTAL_{address.EMI}", credit=True, **common_args
            ),
        ]

    def expected_clear_internal_contra_postings(
        self,
        amount: Decimal,
    ) -> list[PostingInstruction]:

        common_args = (
            dict(
                amount=amount,
                client_transaction_id=f"REBALANCE_HISTORIC_REPAYMENTS_{self.hook_execution_id}",
            )
            | self.COMMON_POSTING_ARGS
        )

        return [
            self.mock_posting_instruction(
                account_id=DEFAULT_LINE_OF_CREDIT_ACCOUNT_ID,
                address=address.DEFAULT,
                credit=False,
                **common_args,
            ),
            self.mock_posting_instruction(
                account_id="Main account",
                address=address.INTERNAL_CONTRA,
                credit=True,
                **common_args,
            ),
        ]

    def test_close_code_with_no_balances_to_clean_up(self):
        mock_vault = self.create_mock(balance_ts=self.account_balances())
        self.run_function(
            "close_code",
            mock_vault,
            effective_date=DEFAULT_DATE,
        )
        mock_vault.instruct_posting_instruction_batch.assert_not_called()

    def test_close_code_with_balances_to_clean_up(self):
        mock_vault = self.create_mock(
            balance_ts=self.account_balances(emi=Decimal("1000"), internal_contra=Decimal("500")),
            line_of_credit_account_id=DEFAULT_LINE_OF_CREDIT_ACCOUNT_ID,
            make_instructions_return_full_objects=True,
        )
        self.run_function(
            "close_code",
            mock_vault,
            effective_date=DEFAULT_DATE,
        )
        mock_vault.instruct_posting_batch.assert_called_once_with(
            posting_instructions=self.expected_clear_emi_postings(amount=Decimal("1000"))
            + self.expected_clear_emi_aggregate_postings(amount=Decimal("1000"))
            # This amount is original contra of 500 + use inside of hook of 1000 to clear emi
            + self.expected_clear_internal_contra_postings(amount=Decimal("1500")),
            effective_date=DEFAULT_DATE,
            client_batch_id="CLEANUP_DRAWDOWN_MOCK_HOOK",
            batch_details={"force_override": "true"},
        )

    def test_close_code_with_debt_still_outstanding(self):
        mock_vault = self.create_mock(balance_ts=self.account_balances(principal=Decimal("1000")))
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "close_code",
                mock_vault,
                effective_date=DEFAULT_DATE,
            )
        self.assertEqual(
            str(e.exception),
            "The loan cannot be closed until all outstanding debt is repaid",
        )
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)


class DerivedParametersTest(DrawdownLoanTest):
    def test_per_loan_early_repayment(self):
        mock_vault = self.create_mock(
            overpayment_fee_percentage=Decimal("0.05"),
            balance_ts=self.account_balances(
                principal=Decimal("100"),
                principal_due=Decimal("100"),
                interest=Decimal("100"),
                interest_due=Decimal("100"),
            ),
            line_of_credit_account_id=DEFAULT_LINE_OF_CREDIT_ACCOUNT_ID,
            make_instructions_return_full_objects=True,
        )
        result = self.run_function(
            "derived_parameters",
            mock_vault,
            DEFAULT_DATE,
        )
        # result should be total = (100 * 4) + (100 * 0.05) = 405
        self.assertEqual(result["per_loan_early_repayment_amount"], Decimal("405"))
