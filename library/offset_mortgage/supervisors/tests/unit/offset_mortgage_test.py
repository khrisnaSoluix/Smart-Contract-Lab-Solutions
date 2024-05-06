# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Tuple
from unittest.mock import call

# common
from inception_sdk.test_framework.contracts.unit.supervisor.common import (
    SupervisorContractTest,
    balance_dimensions,
    create_posting_instruction_batch_directive,
)
from inception_sdk.vault.contracts.supervisor.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Balance,
    BalanceDefaultDict,
    HookDirectives,
    Phase,
    PostingInstructionBatchDirective,
    Tside,
)

CONTRACT_FILE = "library/offset_mortgage/supervisors/offset_mortgage.py"
MORTGAGE_CONTRACT_FILE = "library/mortgage/contracts/mortgage.py"
CASA_CONTRACT_FILE = "library/casa/contracts/casa.py"

DEFAULT_DENOMINATION = "GBP"
DEFAULT_DATE = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)

MORTGAGE_ACCOUNT = "MORTGAGE_ACCOUNT"
EAS_ACCOUNT = "EAS_ACCOUNT"
CA_ACCOUNT = "CA_ACCOUNT"
DEPOSIT_ACCOUNT = "DEPOSIT_ACCOUNT"

INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTERNAL_CAPITALISED_INTEREST_RECEIVED_ACCOUNT = "CAPITALISED_INTEREST_RECEIVED"
INTERNAL_INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
INTERNAL_PENALTY_INTEREST_RECEIVED_ACCOUNT = "PENALTY_INTEREST_RECEIVED"
INTERNAL_LATE_REPAYMENT_FEE_INCOME_ACCOUNT = "LATE_REPAYMENT_FEE_INCOME"
INTERNAL_OVERPAYMENT_ALLOWANCE_FEE_INCOME_ACCOUNT = "OVERPAYMENT_ALLOWANCE_FEE_INCOME"

PRINCIPAL = "PRINCIPAL"
ACCRUED_EXPECTED_INTEREST = "ACCRUED_EXPECTED_INTEREST"
INTEREST_DUE = "INTEREST_DUE"
PRINCIPAL_DUE = "PRINCIPAL_DUE"
OVERPAYMENT = "OVERPAYMENT"
EMI_PRINCIPAL_EXCESS = "EMI_PRINCIPAL_EXCESS"
INTEREST_OVERDUE = "INTEREST_OVERDUE"
PRINCIPAL_OVERDUE = "PRINCIPAL_OVERDUE"
PENALTIES = "PENALTIES"
EMI_ADDRESS = "EMI"
ACCRUED_INTEREST = "ACCRUED_INTEREST"
INTERNAL_CONTRA = "INTERNAL_CONTRA"

PENALTIES_ADDRESS = "PENALTIES"


class OffsetMortgageSupervisorTest(SupervisorContractTest):
    # This is needed to enable posting mocks, but has no impact today as
    # supervisors do not support the `.balances()` methods
    side = Tside.LIABILITY
    contract_files = {
        "supervisor": CONTRACT_FILE,
        "mortgage": MORTGAGE_CONTRACT_FILE,
        "eas": CASA_CONTRACT_FILE,
        "ca": CASA_CONTRACT_FILE,
    }

    def balances_for_mortgage(
        self,
        dt=DEFAULT_DATE,
        principal=Decimal(0),
        accrued_interest=Decimal(0),
        principal_due=Decimal(0),
        interest_due=Decimal(0),
        fees=Decimal(0),
        in_arrears_accrued=Decimal(0),
        overpayment=Decimal(0),
        emi_principal_excess=Decimal(0),
        principal_overdue=Decimal(0),
        interest_overdue=Decimal(0),
        default_committed=Decimal(0),
        expected_accrued_interest=Decimal(0),
        emi=Decimal(0),
        nonexistant_address=Decimal(0),
    ) -> List[Tuple[datetime, BalanceDefaultDict]]:

        balance_dict = {
            balance_dimensions(): Balance(net=default_committed),
            balance_dimensions(address="PRINCIPAL"): Balance(net=principal),
            balance_dimensions(address="ACCRUED_INTEREST"): Balance(net=accrued_interest),
            balance_dimensions(address="PRINCIPAL_DUE"): Balance(net=principal_due),
            balance_dimensions(address="INTEREST_DUE"): Balance(net=interest_due),
            balance_dimensions(address="PENALTIES"): Balance(net=fees),
            balance_dimensions(address="IN_ARREARS_ACCRUED"): Balance(net=in_arrears_accrued),
            balance_dimensions(address="PRINCIPAL_OVERDUE"): Balance(net=principal_overdue),
            balance_dimensions(address="OVERPAYMENT"): Balance(net=overpayment),
            balance_dimensions(address="ACCRUED_EXPECTED_INTEREST"): Balance(
                net=expected_accrued_interest
            ),
            balance_dimensions(address="EMI_PRINCIPAL_EXCESS"): Balance(net=emi_principal_excess),
            balance_dimensions(address="INTEREST_OVERDUE"): Balance(net=interest_overdue),
            balance_dimensions(address="EMI"): Balance(net=emi),
            balance_dimensions(address="nonexistant_address"): Balance(net=nonexistant_address),
        }
        balance_defaultdict = BalanceDefaultDict(lambda: Balance(net=0), balance_dict)
        return [(dt, balance_defaultdict)]

    def balances_for_easy_access_saver(
        self,
        dt=DEFAULT_DATE,
        accrued_payable=Decimal(0),
        default_committed=Decimal(0),
        accrued_receivable=Decimal(0),
        overdraft_fee=Decimal(0),
        internal_contra=Decimal(0),
    ) -> List[Tuple[datetime, BalanceDefaultDict]]:

        balance_dict = {
            balance_dimensions(denomination=DEFAULT_DENOMINATION): Balance(net=default_committed),
            balance_dimensions(
                denomination=DEFAULT_DENOMINATION, address="ACCRUED_INTEREST_PAYABLE"
            ): Balance(net=accrued_payable),
            balance_dimensions(
                denomination=DEFAULT_DENOMINATION, address="ACCRUED_INTEREST_RECEIVABLE"
            ): Balance(net=accrued_receivable),
            balance_dimensions(denomination=DEFAULT_DENOMINATION, address="OVERDRAFT_FEE"): Balance(
                net=overdraft_fee
            ),
            balance_dimensions(
                denomination=DEFAULT_DENOMINATION, address="INTERNAL_CONTRA"
            ): Balance(net=internal_contra),
            balance_dimensions(denomination=DEFAULT_DENOMINATION, phase=Phase.COMMITTED): Balance(
                net=default_committed
            ),
        }

        balance_defaultdict = BalanceDefaultDict(lambda: Balance(net=Decimal(0)), balance_dict)
        return [(dt, balance_defaultdict)]

    def balances_for_current_account(
        self,
        dt=DEFAULT_DATE,
        default_committed=Decimal(0),
    ) -> List[Tuple[datetime, BalanceDefaultDict]]:
        balance_defaultdict = BalanceDefaultDict(
            lambda: Balance(net=0),
            {balance_dimensions(denomination=DEFAULT_DENOMINATION): Balance(net=default_committed)},
        )
        return [(dt, balance_defaultdict)]

    def create_mortgage_interest_accrual_postings(
        self,
        accrual_amount,
        daily_interest_rate,
        outstanding_principal,
        denomination=DEFAULT_DENOMINATION,
        expected_accrual_amount=None,
        expected_principal=None,
    ):
        expected_accrual_amount = expected_accrual_amount or accrual_amount
        expected_principal = expected_principal or outstanding_principal

        accrual_instruction_details = {
            "description": f"Daily interest accrued at {daily_interest_rate*100:0.6f}%"
            f" on outstanding principal of {outstanding_principal}",
            "event_type": "ACCRUE_INTEREST",
            "daily_interest_rate": f"{daily_interest_rate}",
        }
        expected_accrual_instruction_details = {
            "description": f"Expected daily interest accrued at {daily_interest_rate*100:0.6f}%"
            f" on expected pricnipal of {expected_principal} and outstanding principal"
            f" of {outstanding_principal}",
            "event_type": "ACCRUE_INTEREST",
            "daily_interest_rate": f"{daily_interest_rate}",
        }

        mortgage_interest_accrual_postings = [
            self.custom_instruction(
                amount=accrual_amount,
                denomination=denomination,
                account_id=MORTGAGE_ACCOUNT,
                account_address=ACCRUED_INTEREST,
                client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                override_all_restrictions=True,
                credit=False,
                instruction_details=accrual_instruction_details,
                phase=Phase.COMMITTED,
            ),
            self.custom_instruction(
                amount=accrual_amount,
                denomination=denomination,
                account_id=MORTGAGE_ACCOUNT,
                account_address=INTERNAL_CONTRA,
                client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_CUSTOMER",
                override_all_restrictions=True,
                credit=True,
                instruction_details=accrual_instruction_details,
                phase=Phase.COMMITTED,
            ),
            self.custom_instruction(
                amount=accrual_amount,
                denomination=denomination,
                account_id=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                account_address=DEFAULT_ADDRESS,
                client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_INTERNAL",
                override_all_restrictions=True,
                credit=False,
                instruction_details=accrual_instruction_details,
                phase=Phase.COMMITTED,
            ),
            self.custom_instruction(
                amount=accrual_amount,
                denomination=denomination,
                account_id=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
                account_address=DEFAULT_ADDRESS,
                client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_INTERNAL",
                override_all_restrictions=True,
                credit=True,
                instruction_details=accrual_instruction_details,
                phase=Phase.COMMITTED,
            ),
        ]
        mortgage_expected_interest_accrual_postings = [
            self.custom_instruction(
                amount=expected_accrual_amount,
                denomination=denomination,
                account_id=MORTGAGE_ACCOUNT,
                account_address=ACCRUED_EXPECTED_INTEREST,
                client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_EXPECTED",
                override_all_restrictions=True,
                credit=False,
                instruction_details=expected_accrual_instruction_details,
                phase=Phase.COMMITTED,
            ),
            self.custom_instruction(
                amount=expected_accrual_amount,
                denomination=denomination,
                account_id=MORTGAGE_ACCOUNT,
                account_address=INTERNAL_CONTRA,
                client_transaction_id="MOCK_HOOK_INTEREST_ACCRUAL_EXPECTED",
                override_all_restrictions=True,
                credit=True,
                instruction_details=expected_accrual_instruction_details,
                phase=Phase.COMMITTED,
            ),
        ]

        return {
            "accrual_postings": mortgage_interest_accrual_postings,
            "expected_accrual_postings": mortgage_expected_interest_accrual_postings,
        }

    def test_accrue_interest_no_supervisees_no_side_effect(self):
        mock_supervisor_vault = self.create_supervisor_mock()

        self.run_function(
            "_accrue_interest",
            mock_supervisor_vault,
            vault=mock_supervisor_vault,
            effective_date=DEFAULT_DATE,
        )

        self.assert_no_side_effects(mock_supervisor_vault)

    def test_accrue_interest_only_mortgage_supervisee_hook_directives_committed(self):
        mortgage_interest_accrual_posting_directive = create_posting_instruction_batch_directive(
            amount=Decimal("0.00274"),
            tside=Tside.ASSET,
            denomination=DEFAULT_DENOMINATION,
            from_account_address=ACCRUED_INTEREST,
            from_account_id=MORTGAGE_ACCOUNT,
            to_account_address=INTERNAL_CONTRA,
            to_account_id=MORTGAGE_ACCOUNT,
            instruction_details={
                "description": "Daily interest accrued at 0.002740%"
                " on outstanding principal of 100",
                "event_type": "ACCRUE_INTEREST",
                "daily_interest_rate": "0.0000273973",
            },
        )
        mortgage_balance = self.balances_for_mortgage(principal=Decimal("100"))

        mock_mortgage_supervisee = self.create_supervisee_mock(
            alias="mortgage",
            account_id=MORTGAGE_ACCOUNT,
            balance_ts=mortgage_balance,
            hook_directives=HookDirectives(
                posting_instruction_batch_directives=[mortgage_interest_accrual_posting_directive]
            ),
        )
        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={MORTGAGE_ACCOUNT: mock_mortgage_supervisee}
        )

        self.run_function(
            "_accrue_interest",
            mock_supervisor_vault,
            vault=mock_supervisor_vault,
            effective_date=DEFAULT_DATE,
        )
        mortgage_interest_accrual_pib = (
            mortgage_interest_accrual_posting_directive.posting_instruction_batch
        )
        mock_mortgage_supervisee.instruct_posting_batch.assert_called_with(
            posting_instructions=mortgage_interest_accrual_pib.posting_instructions,
            effective_date=DEFAULT_DATE,
        )

    def test_accrue_interest_only_mortgage_supervisee_no_hook_directive_no_side_effects(
        self,
    ):
        mortgage_balance = self.balances_for_mortgage(principal=Decimal("100"))

        mock_mortgage_supervisee = self.create_supervisee_mock(
            alias="mortgage",
            account_id=MORTGAGE_ACCOUNT,
            balance_ts=mortgage_balance,
            hook_directives=HookDirectives(),
        )
        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={MORTGAGE_ACCOUNT: mock_mortgage_supervisee}
        )

        self.run_function(
            "_accrue_interest",
            mock_supervisor_vault,
            vault=mock_supervisor_vault,
            effective_date=DEFAULT_DATE,
        )

        self.assert_no_side_effects(mock_mortgage_supervisee)

    def test_accrue_interest_only_eas_supervisee_hook_directives_committed(self):
        eas_balance = self.balances_for_easy_access_saver(default_committed=Decimal("100"))

        eas_interest_accrual_posting_directive = create_posting_instruction_batch_directive(
            amount=Decimal("0.00274"),
            tside=Tside.ASSET,
            denomination=DEFAULT_DENOMINATION,
            from_account_address=ACCRUED_INTEREST,
            from_account_id=MORTGAGE_ACCOUNT,
            to_account_address=INTERNAL_CONTRA,
            to_account_id=MORTGAGE_ACCOUNT,
            instruction_details={
                "description": "Daily interest accrued at 0.002740%" " on balance of 100",
                "event_type": "ACCRUE_INTEREST",
            },
        )

        mock_eas_supervisee = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=EAS_ACCOUNT,
            balance_ts=eas_balance,
            hook_directives=HookDirectives(
                posting_instruction_batch_directives=[eas_interest_accrual_posting_directive]
            ),
        )
        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={EAS_ACCOUNT: mock_eas_supervisee}
        )

        self.run_function(
            "_accrue_interest",
            mock_supervisor_vault,
            vault=mock_supervisor_vault,
            effective_date=DEFAULT_DATE,
        )
        eas_interest_accrual_pib = eas_interest_accrual_posting_directive.posting_instruction_batch
        mock_eas_supervisee.instruct_posting_batch.assert_called_with(
            posting_instructions=eas_interest_accrual_pib.posting_instructions,
            effective_date=DEFAULT_DATE,
        )

    def test_accrue_interest_only_eas_supervisee_no_hook_directive_no_side_effects(
        self,
    ):
        eas_balance = self.balances_for_easy_access_saver(default_committed=Decimal("100"))

        mock_eas_supervisee = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=EAS_ACCOUNT,
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
        )
        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={EAS_ACCOUNT: mock_eas_supervisee}
        )

        self.run_function(
            "_accrue_interest",
            mock_supervisor_vault,
            vault=mock_supervisor_vault,
            effective_date=DEFAULT_DATE,
        )

        self.assert_no_side_effects(mock_eas_supervisee)

    def test_accrue_interest_different_denomination_no_hook_directives_no_side_effects(
        self,
    ):
        mortgage_balance = self.balances_for_mortgage(principal=Decimal("100"))
        ca_balance = self.balances_for_current_account(default_committed=Decimal("0"))
        eas_balance = self.balances_for_easy_access_saver(default_committed=Decimal("100"))

        mock_mortgage_supervisee = self.create_supervisee_mock(
            alias="mortgage",
            balance_ts=mortgage_balance,
            denomination=DEFAULT_DENOMINATION,
            account_id=MORTGAGE_ACCOUNT,
            hook_directives=HookDirectives(),
        )
        mock_eas_supervisee = self.create_supervisee_mock(
            alias="easy_access_saver",
            balance_ts=eas_balance,
            account_id=EAS_ACCOUNT,
            hook_directives=HookDirectives(),
        )
        mock_ca_supervisee = self.create_supervisee_mock(
            alias="current_account",
            balance_ts=ca_balance,
            account_id=CA_ACCOUNT,
            hook_directives=HookDirectives(),
        )
        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={
                MORTGAGE_ACCOUNT: mock_mortgage_supervisee,
                EAS_ACCOUNT: mock_eas_supervisee,
                CA_ACCOUNT: mock_ca_supervisee,
            }
        )

        self.run_function(
            "_accrue_interest",
            mock_supervisor_vault,
            vault=mock_supervisor_vault,
            effective_date=DEFAULT_DATE,
        )

        self.assert_no_side_effects(mock_mortgage_supervisee)
        self.assert_no_side_effects(mock_eas_supervisee)
        self.assert_no_side_effects(mock_ca_supervisee)

    def test_accrue_interest_different_denomination_commits_hook_directives(self):
        mortgage_interest_accrual_posting_directive = create_posting_instruction_batch_directive(
            amount=Decimal("0.00274"),
            tside=Tside.ASSET,
            denomination=DEFAULT_DENOMINATION,
            from_account_address=ACCRUED_INTEREST,
            from_account_id=MORTGAGE_ACCOUNT,
            to_account_address=INTERNAL_CONTRA,
            to_account_id=MORTGAGE_ACCOUNT,
            instruction_details={
                "description": "Daily interest accrued at 0.002740%"
                " on outstanding principal of 100",
                "event_type": "ACCRUE_INTEREST",
                "daily_interest_rate": "0.0000273973",
            },
        )
        eas_interest_accrual_posting_directive = create_posting_instruction_batch_directive(
            amount=Decimal("0.00274"),
            tside=Tside.ASSET,
            denomination=DEFAULT_DENOMINATION,
            from_account_address=ACCRUED_INTEREST,
            from_account_id=MORTGAGE_ACCOUNT,
            to_account_address=INTERNAL_CONTRA,
            to_account_id=MORTGAGE_ACCOUNT,
            instruction_details={
                "description": "Daily interest accrued at 0.002740%" " on balance of 100",
                "event_type": "ACCRUE_INTEREST",
            },
        )
        mock_mortgage_supervisee = self.create_supervisee_mock(
            alias="mortgage",
            account_id=MORTGAGE_ACCOUNT,
            hook_directives=HookDirectives(
                posting_instruction_batch_directives=[mortgage_interest_accrual_posting_directive]
            ),
            denomination="HKD",
        )
        mock_eas_supervisee = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=EAS_ACCOUNT,
            hook_directives=HookDirectives(
                posting_instruction_batch_directives=[eas_interest_accrual_posting_directive]
            ),
            denomination="USD",
        )
        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={
                MORTGAGE_ACCOUNT: mock_mortgage_supervisee,
                EAS_ACCOUNT: mock_eas_supervisee,
            }
        )

        self.run_function(
            "_accrue_interest",
            mock_supervisor_vault,
            vault=mock_supervisor_vault,
            effective_date=DEFAULT_DATE,
        )

        mortgage_interest_accrual_pib = (
            mortgage_interest_accrual_posting_directive.posting_instruction_batch
        )
        mock_mortgage_supervisee.instruct_posting_batch.assert_called_with(
            posting_instructions=mortgage_interest_accrual_pib.posting_instructions,
            effective_date=DEFAULT_DATE,
        )
        eas_interest_accrual_pib = eas_interest_accrual_posting_directive.posting_instruction_batch
        mock_eas_supervisee.instruct_posting_batch.assert_called_with(
            posting_instructions=eas_interest_accrual_pib.posting_instructions,
            effective_date=DEFAULT_DATE,
        )

    def test_accrue_interest_offset_interest_accrual_no_savings_balance_no_offset(self):
        mortgage_balance = self.balances_for_mortgage(principal=Decimal("100"))
        eas_balance = self.balances_for_easy_access_saver(default_committed=Decimal("0"))
        mortgage_interest_accrual_postings = self.create_mortgage_interest_accrual_postings(
            Decimal("0.00274"), Decimal("0.0000273973"), Decimal("100")
        )
        mock_mortgage_supervisee = self.create_supervisee_mock(
            alias="mortgage",
            account_id=MORTGAGE_ACCOUNT,
            balance_ts=mortgage_balance,
            hook_directives=HookDirectives(
                posting_instruction_batch_directives=[
                    PostingInstructionBatchDirective(
                        posting_instruction_batch=self.mock_posting_instruction_batch(
                            posting_instructions=(
                                mortgage_interest_accrual_postings["accrual_postings"]
                                + mortgage_interest_accrual_postings["expected_accrual_postings"]
                            ),
                        )
                    )
                ]
            ),
            denomination=DEFAULT_DENOMINATION,
            interest_received_account=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
            accrued_interest_receivable_account=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
            accrual_precision=5,
        )
        mock_eas_supervisee = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=EAS_ACCOUNT,
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )
        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={
                MORTGAGE_ACCOUNT: mock_mortgage_supervisee,
                EAS_ACCOUNT: mock_eas_supervisee,
            }
        )

        self.run_function(
            "_accrue_interest",
            mock_supervisor_vault,
            vault=mock_supervisor_vault,
            effective_date=DEFAULT_DATE,
        )

        self.assert_no_side_effects(mock_eas_supervisee)
        mock_mortgage_supervisee.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal("0.00274"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_OFFSET_INTEREST_ACCRUAL_CUSTOMER",
                    from_account_id=MORTGAGE_ACCOUNT,
                    from_account_address=ACCRUED_INTEREST,
                    to_account_id=MORTGAGE_ACCOUNT,
                    to_account_address=INTERNAL_CONTRA,
                    instruction_details={
                        "description": "Daily offset interest accrued at 0.002740% on outstanding"
                        " principal of 100 offset with balance of 0",
                        "event_type": "ACCRUE_OFFSET_INTEREST",
                    },
                ),
                call(
                    amount=Decimal("0.00274"),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="MOCK_HOOK_OFFSET_INTEREST_ACCRUAL_INTERNAL",
                    from_account_id=INTERNAL_ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
                    from_account_address=DEFAULT_ADDRESS,
                    to_account_id=INTERNAL_INTEREST_RECEIVED_ACCOUNT,
                    to_account_address=DEFAULT_ADDRESS,
                    instruction_details={
                        "description": "Daily offset interest accrued at 0.002740% on outstanding"
                        " principal of 100 offset with balance of 0",
                        "event_type": "ACCRUE_OFFSET_INTEREST",
                    },
                ),
            ]
        )
        mock_mortgage_supervisee.instruct_posting_batch.assert_called_with(
            posting_instructions=(
                mortgage_interest_accrual_postings["expected_accrual_postings"]
                + [
                    "MOCK_HOOK_OFFSET_INTEREST_ACCRUAL_CUSTOMER",
                    "MOCK_HOOK_OFFSET_INTEREST_ACCRUAL_INTERNAL",
                ]
            ),
            effective_date=DEFAULT_DATE,
        )

    def test_accrue_interest_with_penalty_interest_postings_applied(self):
        """
        Test penalty interesting posting is applied.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)

        # setup easy access saver supervisee
        eas_balance = self.balances_for_easy_access_saver(default_committed=Decimal("0"))
        mock_eas_supervisee = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=EAS_ACCOUNT,
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        # setup mortgage supervisee
        account_id = "000001"
        penalty_interest = Decimal(123)
        mortgage_balance = self.balances_for_mortgage(principal=Decimal("0"))

        pib_directive = create_posting_instruction_batch_directive(
            tside=Tside.ASSET,
            amount=penalty_interest,
            denomination=DEFAULT_DENOMINATION,
            from_account_address=PENALTIES_ADDRESS,
            from_account_id=account_id,
            to_account_address=DEFAULT_ADDRESS,
            to_account_id=INTERNAL_CONTRA,
            client_transaction_id="MOCK_HOOK_ACCRUE_PENALTY_INTEREST",
            instruction_details={
                "description": "Penalty interest accrual on overdue amount",
                "event": "ACCRUE_PENALTY_INTEREST",
            },
        )

        mock_mortgage_supervisee = self.create_supervisee_mock(
            alias="mortgage",
            account_id=account_id,
            balance_ts=mortgage_balance,
            hook_directives=HookDirectives(posting_instruction_batch_directives=[pib_directive]),
            tside=Tside.ASSET,
            creation_date=start,
            denomination=DEFAULT_DENOMINATION,
            accrual_precision=5,
        )

        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={
                MORTGAGE_ACCOUNT: mock_mortgage_supervisee,
                EAS_ACCOUNT: mock_eas_supervisee,
            }
        )

        self.run_function(
            "_accrue_interest",
            mock_supervisor_vault,
            vault=mock_supervisor_vault,
            effective_date=DEFAULT_DATE,
        )

        pib = pib_directive.posting_instruction_batch
        mock_mortgage_supervisee.instruct_posting_batch.assert_called_with(
            effective_date=DEFAULT_DATE, posting_instructions=pib
        )


class HelperFunctionTest(OffsetMortgageSupervisorTest):
    def test_get_available_balance_returns_available_balance_on_eas(self):
        expected = 50

        balances = {
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=100),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.PENDING_OUT,
            ): Balance(net=-50),
        }

        result = self.run_function(
            "_get_available_balance",
            None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_get_available_balance_0_default_balance_on_eas(self):
        expected = -50

        balances = {
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=0),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.PENDING_OUT,
            ): Balance(net=-50),
        }

        result = self.run_function(
            "_get_available_balance",
            None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_get_available_balance_0_pending_out_balance_on_eas(self):
        expected = 100

        balances = {
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=100),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.PENDING_OUT,
            ): Balance(net=0),
        }

        result = self.run_function(
            "_get_available_balance",
            None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_get_available_balance_0_pending_in_balance_on_eas(self):
        expected = 100

        balances = {
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=100),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.PENDING_OUT,
            ): Balance(net=0),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.PENDING_IN,
            ): Balance(net=50),
        }

        result = self.run_function(
            "_get_available_balance",
            None,
            balances=balances,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_get_balance_sum_single_address(self):
        balance_ts = self.balances_for_mortgage(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            overpayment=Decimal("-150"),
            fees=Decimal("325"),
            principal_overdue=Decimal("123"),
            interest_overdue=Decimal("22.33"),
            nonexistant_address=Decimal("2"),
        )

        mock_supervisee_vault = self.create_supervisee_mock(
            alias="mortgage",
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
        )

        addresses = ["PRINCIPAL"]

        result = self.run_function(
            "_get_balance_sum",
            mock_supervisee_vault,
            vault=mock_supervisee_vault,
            addresses=addresses,
        )

        self.assertEqual(result, Decimal("100000"))

    def test_get_balance_sum_multi_addresses(self):
        balance_ts = self.balances_for_mortgage(
            DEFAULT_DATE,
            principal_due=Decimal("100"),
            interest_due=Decimal("35.00"),
            principal=Decimal("100000"),
            overpayment=Decimal("-150"),
            fees=Decimal("325"),
            principal_overdue=Decimal("123"),
            interest_overdue=Decimal("22.33"),
            nonexistant_address=Decimal("2"),
        )

        mock_supervisee_vault = self.create_supervisee_mock(
            alias="mortgage",
            balance_ts=balance_ts,
            denomination=DEFAULT_DENOMINATION,
        )

        addresses = ["PRINCIPAL", "OVERPAYMENT", "PENALTIES"]

        result = self.run_function(
            "_get_balance_sum",
            mock_supervisee_vault,
            vault=mock_supervisee_vault,
            addresses=addresses,
        )

        self.assertEqual(result, Decimal("100175"))

    def test_precision_doesnt_round_less_dp(self):
        rounded_amount = self.run_function(
            "_round_to_precision", None, precision=5, amount=Decimal("1.11")
        )

        self.assertEqual(rounded_amount, Decimal("1.11000"))

    def test_round_to_precision_0dp(self):
        rounded_amount = self.run_function(
            "_round_to_precision", None, precision=0, amount=Decimal("1.1111111")
        )

        self.assertEqual(rounded_amount, Decimal("1.0"))

    def test_round_to_precision_5dp(self):
        rounded_amount = self.run_function(
            "_round_to_precision", None, precision=5, amount=Decimal("1.1111111")
        )

        self.assertEqual(rounded_amount, Decimal("1.11111"))

    def test_round_to_precision_15dp(self):
        rounded_amount = self.run_function(
            "_round_to_precision",
            None,
            precision=15,
            amount=Decimal("1.1111111111111111111"),
        )

        self.assertEqual(rounded_amount, Decimal("1.111111111111111"))

    def test_split_accounts_by_denomination_on_eas_one_different(self):
        # setup easy access saver supervisee
        eas_balance = self.balances_for_easy_access_saver(default_committed=Decimal("0"))
        mock_eas_supervisee_1 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 0",
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        mock_eas_supervisee_2 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 1",
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination="HKD",
        )

        mock_eas_supervisee_3 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 2",
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination="HKD",
        )

        offset_accounts_list = [
            mock_eas_supervisee_1,
            mock_eas_supervisee_2,
            mock_eas_supervisee_3,
        ]

        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={
                f"{EAS_ACCOUNT} 0": mock_eas_supervisee_1,
                f"{EAS_ACCOUNT} 1": mock_eas_supervisee_2,
                f"{EAS_ACCOUNT} 2": mock_eas_supervisee_3,
            }
        )

        expected = (
            [mock_eas_supervisee_1],
            [mock_eas_supervisee_2, mock_eas_supervisee_3],
        )

        result = self.run_function(
            "_split_accounts_by_denomination",
            mock_supervisor_vault,
            offset_accounts=offset_accounts_list,
            mortgage_denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_split_accounts_by_denomination_on_eas_all_same(self):
        # setup easy access saver supervisee
        eas_balance = self.balances_for_easy_access_saver(default_committed=Decimal("0"))
        mock_eas_supervisee_1 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 0",
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        mock_eas_supervisee_2 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 1",
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        offset_accounts_list = [mock_eas_supervisee_1, mock_eas_supervisee_2]

        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={
                f"{EAS_ACCOUNT} 0": mock_eas_supervisee_1,
                f"{EAS_ACCOUNT} 1": mock_eas_supervisee_2,
            }
        )

        expected = ([mock_eas_supervisee_1, mock_eas_supervisee_2], [])

        result = self.run_function(
            "_split_accounts_by_denomination",
            mock_supervisor_vault,
            offset_accounts=offset_accounts_list,
            mortgage_denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_split_accounts_by_denomination_on_eas_all_different(self):
        # setup easy access saver supervisee
        eas_balance = self.balances_for_easy_access_saver(default_committed=Decimal("0"))
        mock_eas_supervisee_1 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 0",
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination="USD",
        )

        mock_eas_supervisee_2 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 1",
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination="HKD",
        )

        offset_accounts_list = [mock_eas_supervisee_1, mock_eas_supervisee_2]

        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={
                f"{EAS_ACCOUNT} 0": mock_eas_supervisee_1,
                f"{EAS_ACCOUNT} 1": mock_eas_supervisee_2,
            }
        )

        expected = ([], [mock_eas_supervisee_1, mock_eas_supervisee_2])

        result = self.run_function(
            "_split_accounts_by_denomination",
            mock_supervisor_vault,
            offset_accounts=offset_accounts_list,
            mortgage_denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_split_accounts_by_balance_positive_balance(self):
        eas_balance = self.balances_for_easy_access_saver(default_committed=Decimal("500"))
        mock_eas_supervisee_1 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 0",
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        mock_eas_supervisee_2 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 1",
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        offset_accounts_list = [mock_eas_supervisee_1, mock_eas_supervisee_2]

        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={
                f"{EAS_ACCOUNT} 0": mock_eas_supervisee_1,
                f"{EAS_ACCOUNT} 1": mock_eas_supervisee_2,
            }
        )

        expected = ([mock_eas_supervisee_1, mock_eas_supervisee_2], [])

        result = self.run_function(
            "_split_accounts_by_balance",
            mock_supervisor_vault,
            offset_accounts=offset_accounts_list,
            mortgage_denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_split_accounts_by_balance_positive_and_negative_balance(self):
        eas_balance = self.balances_for_easy_access_saver(default_committed=Decimal("500"))
        ca_negative_balance = self.balances_for_current_account(default_committed=Decimal("-500"))
        mock_eas_supervisee_1 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 0",
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        mock_ca_supervisee_2 = self.create_supervisee_mock(
            alias="current_account",
            account_id=f"{CA_ACCOUNT} 1",
            balance_ts=ca_negative_balance,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        offset_accounts_list = [mock_eas_supervisee_1, mock_ca_supervisee_2]

        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={
                f"{EAS_ACCOUNT} 0": mock_eas_supervisee_1,
                f"{CA_ACCOUNT} 1": mock_ca_supervisee_2,
            }
        )

        expected = ([mock_eas_supervisee_1], [mock_ca_supervisee_2])

        result = self.run_function(
            "_split_accounts_by_balance",
            mock_supervisor_vault,
            offset_accounts=offset_accounts_list,
            mortgage_denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_split_accounts_by_balance_negative_balance(self):
        eas_balance = self.balances_for_easy_access_saver(default_committed=Decimal("-700"))
        ca_negative_balance = self.balances_for_current_account(default_committed=Decimal("-500"))
        mock_eas_supervisee_1 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 0",
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        mock_ca_supervisee_2 = self.create_supervisee_mock(
            alias="current_account",
            account_id=f"{CA_ACCOUNT} 1",
            balance_ts=ca_negative_balance,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        offset_accounts_list = [mock_eas_supervisee_1, mock_ca_supervisee_2]

        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={
                f"{EAS_ACCOUNT} 0": mock_eas_supervisee_1,
                f"{CA_ACCOUNT} 1": mock_ca_supervisee_2,
            }
        )

        expected = ([], [mock_eas_supervisee_1, mock_ca_supervisee_2])

        result = self.run_function(
            "_split_accounts_by_balance",
            mock_supervisor_vault,
            offset_accounts=offset_accounts_list,
            mortgage_denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_split_accounts_by_balance_zero_balance(self):
        eas_balance = self.balances_for_easy_access_saver(default_committed=Decimal("0"))
        ca_balance = self.balances_for_current_account(default_committed=Decimal("0"))
        mock_eas_supervisee_1 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 0",
            balance_ts=eas_balance,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        mock_ca_supervisee_2 = self.create_supervisee_mock(
            alias="current_account",
            account_id=f"{CA_ACCOUNT} 1",
            balance_ts=ca_balance,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        offset_accounts_list = [mock_eas_supervisee_1, mock_ca_supervisee_2]

        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={
                f"{EAS_ACCOUNT} 0": mock_eas_supervisee_1,
                f"{CA_ACCOUNT} 1": mock_ca_supervisee_2,
            }
        )

        expected = ([mock_eas_supervisee_1, mock_ca_supervisee_2], [])

        result = self.run_function(
            "_split_accounts_by_balance",
            mock_supervisor_vault,
            offset_accounts=offset_accounts_list,
            mortgage_denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(result, expected)

    def test_get_accounts_available_balance_negative_balance(self):
        # setup easy access saver supervisee
        eas_balance_1 = self.balances_for_easy_access_saver(default_committed=Decimal("10000"))
        eas_balance_2 = self.balances_for_easy_access_saver(default_committed=Decimal("-5000"))
        eas_balance_3 = self.balances_for_easy_access_saver(default_committed=Decimal("0"))
        mock_eas_supervisee_1 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 0",
            balance_ts=eas_balance_1,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        mock_eas_supervisee_2 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 1",
            balance_ts=eas_balance_2,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        mock_eas_supervisee_3 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 2",
            balance_ts=eas_balance_3,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        offset_accounts_list = [
            mock_eas_supervisee_1,
            mock_eas_supervisee_2,
            mock_eas_supervisee_3,
        ]

        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={
                f"{EAS_ACCOUNT} 0": mock_eas_supervisee_1,
                f"{EAS_ACCOUNT} 1": mock_eas_supervisee_2,
                f"{EAS_ACCOUNT} 2": mock_eas_supervisee_3,
            }
        )

        result = self.run_function(
            "_get_accounts_available_balance",
            mock_supervisor_vault,
            accounts=offset_accounts_list,
        )

        expected = Decimal(10000)

        self.assertEqual(result, expected)

    def test_get_accounts_available_balance_all_balances(self):
        # setup easy access saver supervisee
        eas_balance_1 = self.balances_for_easy_access_saver(default_committed=Decimal("10000"))
        eas_balance_2 = self.balances_for_easy_access_saver(default_committed=Decimal("5000"))
        eas_balance_3 = self.balances_for_easy_access_saver(default_committed=Decimal("15000"))
        mock_eas_supervisee_1 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 0",
            balance_ts=eas_balance_1,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        mock_eas_supervisee_2 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 1",
            balance_ts=eas_balance_2,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        mock_eas_supervisee_3 = self.create_supervisee_mock(
            alias="easy_access_saver",
            account_id=f"{EAS_ACCOUNT} 2",
            balance_ts=eas_balance_3,
            hook_directives=HookDirectives(),
            denomination=DEFAULT_DENOMINATION,
        )

        offset_accounts_list = [
            mock_eas_supervisee_1,
            mock_eas_supervisee_2,
            mock_eas_supervisee_3,
        ]

        mock_supervisor_vault = self.create_supervisor_mock(
            supervisees={
                f"{EAS_ACCOUNT} 0": mock_eas_supervisee_1,
                f"{EAS_ACCOUNT} 1": mock_eas_supervisee_2,
                f"{EAS_ACCOUNT} 2": mock_eas_supervisee_3,
            }
        )

        result = self.run_function(
            "_get_accounts_available_balance",
            mock_supervisor_vault,
            accounts=offset_accounts_list,
        )

        expected = Decimal(30000)

        self.assertEqual(result, expected)
