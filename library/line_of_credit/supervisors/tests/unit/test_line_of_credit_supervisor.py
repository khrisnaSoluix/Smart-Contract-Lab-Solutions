# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from decimal import Decimal
from json import dumps
from typing import Optional
from unittest.mock import call, ANY

# third party
from dateutil.relativedelta import relativedelta

# common
from inception_sdk.test_framework.contracts.unit.common import DEFAULT_DENOMINATION
from inception_sdk.test_framework.contracts.unit.supervisor.common import (
    SupervisorContractTest,
    balance_dimensions,
)
from inception_sdk.vault.contracts.supervisor.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Balance,
    BalancesObservation,
    Tside,
    BalanceDefaultDict,
    Rejected,
    RejectedReason,
    EventTypeSchedule,
    Phase,
    PostingInstruction,
    PostingInstructionBatch,
    PostingInstructionType,
    UnionItem,
    UnionItemValue,
)
from inception_sdk.vault.contracts.types_extension import INTERNAL_CONTRA

# other
import library.features.lending.debt_management as debt_management
import library.features.lending.disbursement as disbursement
import library.features.lending.interest_accrual as interest_accrual
import library.features.lending.interest_application as interest_application
import library.features.lending.overpayment as overpayment

import library.line_of_credit.constants.addresses as address
import library.line_of_credit.constants.accounts as accounts
import library.line_of_credit.constants.files as files
import library.line_of_credit.constants.repayment_hierarchies as repayment_hierarchies
import library.line_of_credit.supervisors.template.line_of_credit_supervisor as supervisor


DEFAULT_DATE = datetime(year=2019, month=1, day=1)
DEFAULT_LOC_ACCOUNT_ID = "loc"
DEFAULT_LOAN_1_ACCOUNT_ID = "loan_1"
DEFAULT_LOAN_2_ACCOUNT_ID = "loan_2"

# Debt Management
DEFAULT_DIMENSIONS = balance_dimensions()
PRINCIPAL_DIMENSIONS = balance_dimensions(address=address.PRINCIPAL)
EMI_DIMENSIONS = balance_dimensions(address=address.EMI)
ACCRUED_RECEIVABLE_DIMENSIONS = balance_dimensions(address=address.ACCRUED_INTEREST_RECEIVABLE)
PRINCIPAL_DUE_DIMENSIONS = balance_dimensions(address=address.PRINCIPAL_DUE)
INTEREST_DUE_DIMENSIONS = balance_dimensions(address=address.INTEREST_DUE)
PRINCIPAL_OVERDUE_DIMENSIONS = balance_dimensions(address=address.PRINCIPAL_OVERDUE)
INTEREST_OVERDUE_DIMENSIONS = balance_dimensions(address=address.INTEREST_OVERDUE)
PENALTIES_DIMENSIONS = balance_dimensions(address=address.PENALTIES)

# Overpayment
ACCRUED_EXPECTED_DIMENSIONS = balance_dimensions(address=address.ACCRUED_EXPECTED_INTEREST)
OVERPAYMENT_DIMENSIONS = balance_dimensions(address=address.OVERPAYMENT)
EMI_PRINCIPAL_EXCESS_DIMENSIONS = balance_dimensions(address=address.EMI_PRINCIPAL_EXCESS)


class LOCTest(SupervisorContractTest):
    target_test_file = files.LOC_SUPERVISOR
    contract_file = files.LOC_SUPERVISOR
    # This is needed to enable posting mocks
    side = Tside.ASSET
    default_denom = DEFAULT_DENOMINATION

    COMMON_POSTING_ARGS = dict(
        denomination=SupervisorContractTest.default_denom,
        instruction_type=PostingInstructionType.CUSTOM_INSTRUCTION,
        phase=Phase.COMMITTED,
        posting_id=None,
        override_all_restrictions=True,
        custom_instruction_grouping_key=ANY,
        client_id=None,
    )

    REPAYMENT_HIERARCHY = [
        [address.PRINCIPAL_OVERDUE],
        [address.INTEREST_OVERDUE],
        [address.PENALTIES],
        [address.PRINCIPAL_DUE],
        [address.INTEREST_DUE],
    ]

    EARLY_REPAYMENT_HIERARCHY = [
        [address.PRINCIPAL_OVERDUE],
        [address.INTEREST_OVERDUE],
        [address.PENALTIES],
        [address.PRINCIPAL_DUE],
        [address.INTEREST_DUE],
        [
            address.PRINCIPAL,
            address.ACCRUED_INTEREST_RECEIVABLE,
        ],
    ]

    def balances_for_loan_account(
        self,
        dt: datetime = DEFAULT_DATE,
        default=Decimal("0"),
        principal=Decimal("1000"),
        emi=Decimal("250"),
        accrued_interest_receivable=Decimal("0"),
        principal_due=Decimal("0"),
        interest_due=Decimal("0"),
        principal_overdue=Decimal("0"),
        interest_overdue=Decimal("0"),
        accrued_expected_interest=Decimal("0"),
        emi_principal_excess=Decimal("0"),
        overpayment=Decimal("0"),
        penalties=Decimal("0"),
    ) -> list[tuple[datetime, BalanceDefaultDict]]:

        balance_default_dict = BalanceDefaultDict(
            lambda: Balance(net=Decimal("0")),
            {
                DEFAULT_DIMENSIONS: Balance(net=default),
                PRINCIPAL_DIMENSIONS: Balance(net=principal),
                ACCRUED_RECEIVABLE_DIMENSIONS: Balance(net=accrued_interest_receivable),
                PRINCIPAL_OVERDUE_DIMENSIONS: Balance(net=principal_overdue),
                INTEREST_OVERDUE_DIMENSIONS: Balance(net=interest_overdue),
                PENALTIES_DIMENSIONS: Balance(net=penalties),
                PRINCIPAL_DUE_DIMENSIONS: Balance(net=principal_due),
                INTEREST_DUE_DIMENSIONS: Balance(net=interest_due),
                ACCRUED_EXPECTED_DIMENSIONS: Balance(net=accrued_expected_interest),
                OVERPAYMENT_DIMENSIONS: Balance(net=overpayment),
                EMI_DIMENSIONS: Balance(net=emi),
                EMI_PRINCIPAL_EXCESS_DIMENSIONS: Balance(net=emi_principal_excess),
            },
        )
        return [(dt, balance_default_dict)]

    def balances_for_loc_account(
        self,
        dt: datetime = DEFAULT_DATE,
        default=Decimal("0"),
        penalties=Decimal("0"),
    ) -> list[tuple[datetime, BalanceDefaultDict]]:

        balance_default_dict = BalanceDefaultDict(
            lambda: Balance(net=Decimal("0")),
            {
                DEFAULT_DIMENSIONS: Balance(net=default),
                PENALTIES_DIMENSIONS: Balance(net=penalties),
            },
        )
        return [(dt, balance_default_dict)]

    def create_default_drawdown_supervisee_mock(
        self,
        account_id,
        balance_ts=None,
        balances_observation_fetchers_mapping: Optional[dict[str, BalancesObservation]] = None,
        total_term=Decimal("12"),
        loan_start_date=DEFAULT_DATE,
        denomination=DEFAULT_DENOMINATION,
        fixed_interest_rate=Decimal("0.031"),
        penalty_interest_rate=Decimal("0.015"),
        penalty_includes_base_rate=UnionItemValue(key="False"),
        make_instructions_return_full_objects=False,
        **kwargs,
    ):
        return self.create_supervisee_mock(
            alias="drawdown_loan",
            account_id=account_id,
            balance_ts=balance_ts,
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping,
            tside=Tside.ASSET,
            total_term=total_term,
            loan_start_date=loan_start_date,
            denomination=denomination,
            fixed_interest_rate=fixed_interest_rate,
            make_instructions_return_full_objects=make_instructions_return_full_objects,
            principal=Decimal("1000"),
            deposit_account=accounts.DEPOSIT_ACCOUNT,
            penalty_interest_rate=penalty_interest_rate,
            penalty_includes_base_rate=penalty_includes_base_rate,
            accrued_interest_receivable_account="accrued_interest_receivable",
            **kwargs,
        )

    def create_default_loc_supervisee_mock(
        self,
        account_id=DEFAULT_LOC_ACCOUNT_ID,
        balance_ts=None,
        balances_observation_fetchers_mapping: Optional[dict[str, BalancesObservation]] = None,
        denomination=DEFAULT_DENOMINATION,
        credit_limit=Decimal("1000"),
        late_repayment_fee=Decimal("25"),
        delinquency_flags=dumps(["ACCOUNT_DELINQUENT"]),
        accrual_blocking_flags=dumps(["REPAYMENT_HOLIDAY"]),
        overdue_amount_calculation_blocking_flags=dumps(["REPAYMENT_HOLIDAY"]),
        delinquency_blocking_flags=dumps(["REPAYMENT_HOLIDAY"]),
        repayment_blocking_flags=dumps(["REPAYMENT_HOLIDAY"]),
        notification_blocking_flags=dumps(["REPAYMENT_HOLIDAY"]),
        flags=None,
        grace_period=Decimal("0"),
        repayment_period=Decimal("5"),
        due_amount_calculation_day=Decimal("10"),
        due_amount_calculation_hour=Decimal("0"),
        due_amount_calculation_minute=Decimal("0"),
        due_amount_calculation_second=Decimal("2"),
        check_overdue_hour=Decimal("0"),
        check_overdue_minute=Decimal("0"),
        check_overdue_second=Decimal("5"),
        check_delinquency_hour=Decimal("0"),
        check_delinquency_minute=Decimal("2"),
        check_delinquency_second=Decimal("0"),
        overpayment_fee_percentage=Decimal("0.05"),
        overpayment_fee_account="overpayment_fee_account",
        late_repayment_fee_income_account="late_repayment_fee_income_account",
        hook_return_data: Optional[Rejected] = None,
        make_instructions_return_full_objects=False,
        **kwargs,
    ):
        return self.create_supervisee_mock(
            alias="line_of_credit",
            account_id=account_id,
            balance_ts=balance_ts,
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping,
            flags=flags or {"ACCOUNT_DELINQUENT": [(DEFAULT_DATE, False)]},
            hook_return_data=hook_return_data,
            tside=Tside.ASSET,
            # parameters
            denomination=denomination,
            credit_limit=credit_limit,
            late_repayment_fee=late_repayment_fee,
            grace_period=grace_period,
            repayment_period=repayment_period,
            check_delinquency_hour=check_delinquency_hour,
            check_delinquency_minute=check_delinquency_minute,
            check_delinquency_second=check_delinquency_second,
            due_amount_calculation_day=due_amount_calculation_day,
            due_amount_calculation_hour=due_amount_calculation_hour,
            due_amount_calculation_minute=due_amount_calculation_minute,
            due_amount_calculation_second=due_amount_calculation_second,
            check_overdue_hour=check_overdue_hour,
            check_overdue_minute=check_overdue_minute,
            check_overdue_second=check_overdue_second,
            overpayment_fee_percentage=overpayment_fee_percentage,
            overpayment_fee_account=overpayment_fee_account,
            late_repayment_fee_income_account=late_repayment_fee_income_account,
            # flags
            accrual_blocking_flags=accrual_blocking_flags,
            delinquency_flags=delinquency_flags,
            overdue_amount_calculation_blocking_flags=overdue_amount_calculation_blocking_flags,
            delinquency_blocking_flags=delinquency_blocking_flags,
            repayment_blocking_flags=repayment_blocking_flags,
            notification_blocking_flags=notification_blocking_flags,
            # other
            make_instructions_return_full_objects=make_instructions_return_full_objects,
            **kwargs,
        )

    def get_default_setup(
        self, loan_1_balance_ts=None, loan_2_balance_ts=None, loc_balance_ts=None
    ):

        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            balance_ts=loan_1_balance_ts,
            make_instructions_return_full_objects=True,
        )

        mock_vault_loan_2 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            balance_ts=loan_2_balance_ts,
            make_instructions_return_full_objects=True,
        )

        mock_vault_loc = self.create_default_loc_supervisee_mock(
            balance_ts=loc_balance_ts,
            make_instructions_return_full_objects=True,
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOAN_2_ACCOUNT_ID: mock_vault_loan_2,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)

        return (mock_vault, mock_vault_loan_1, mock_vault_loan_2, mock_vault_loc)

    def get_default_setup_with_observation_fetchers(
        self,
        loan_1_balances_observation_fetchers_mapping=None,
        loan_2_balances_observation_fetchers_mapping=None,
        loc_balances_observation_fetchers_mapping=None,
    ):

        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            balances_observation_fetchers_mapping=loan_1_balances_observation_fetchers_mapping,
            make_instructions_return_full_objects=True,
        )

        mock_vault_loan_2 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            balances_observation_fetchers_mapping=loan_2_balances_observation_fetchers_mapping,
            make_instructions_return_full_objects=True,
        )

        mock_vault_loc = self.create_default_loc_supervisee_mock(
            balances_observation_fetchers_mapping=loc_balances_observation_fetchers_mapping,
            make_instructions_return_full_objects=True,
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOAN_2_ACCOUNT_ID: mock_vault_loan_2,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)

        return (mock_vault, mock_vault_loan_1, mock_vault_loan_2, mock_vault_loc)

    def expected_repayment_postings(
        self,
        loan_account_id: str,
        repayment_address: str,
        amount: Decimal,
        repayment_from_address: str = INTERNAL_CONTRA,
    ) -> list[PostingInstruction]:

        instruction_details = {
            "description": f"Repayment of address: {repayment_address} for loan {loan_account_id}",
            "event": "REPAYMENT",
        }
        common_args = (
            dict(
                amount=amount,
                client_transaction_id=f"{repayment_address}_REPAYMENT_FROM"
                + f"_{loan_account_id}_MOCK_HOOK",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )
        return [
            self.mock_posting_instruction(
                account_id=loan_account_id,
                address=repayment_from_address,
                credit=False,
                **common_args,
            ),
            self.mock_posting_instruction(
                account_id=loan_account_id,
                address=repayment_address,
                credit=True,
                **common_args,
            ),
        ]

    def expected_overpayment_tracker_postings(
        self,
        loan_account_id: str,
    ) -> list[PostingInstruction]:

        common_args = (
            dict(
                amount=Decimal("1"),
                client_transaction_id="TRACK_OVERPAYMENT_MOCK_HOOK",
                instruction_details={},
            )
            | self.COMMON_POSTING_ARGS
        )
        return [
            self.mock_posting_instruction(
                account_id=loan_account_id,
                address=address.OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC,
                credit=False,
                **common_args,
            ),
            self.mock_posting_instruction(
                account_id=loan_account_id,
                address=address.INTERNAL_CONTRA,
                credit=True,
                **common_args,
            ),
        ]

    def expected_overpayment_fee_postings(
        self, amount: Decimal, loc_account_id: str = DEFAULT_LOC_ACCOUNT_ID
    ) -> list[PostingInstruction]:

        instruction_details = {
            "description": f"Charging {self.default_denom} {amount} overpayment fee",
            "event": "REPAYMENT",
        }
        common_args = (
            dict(
                amount=amount,
                client_transaction_id="CHARGE_OVERPAYMENT_FEE_MOCK_HOOK",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )
        return [
            self.mock_posting_instruction(
                account_id=loc_account_id,
                address=address.DEFAULT,
                credit=False,
                **common_args,
            ),
            self.mock_posting_instruction(
                account_id="overpayment_fee_account",
                address=address.DEFAULT,
                credit=True,
                **common_args,
            ),
        ]

    def expected_late_repayment_fee_postings(
        self, amount: Decimal, loc_account_id: str = DEFAULT_LOC_ACCOUNT_ID
    ) -> list[PostingInstruction]:

        instruction_details = {
            "description": f"Incur late repayment fees of {amount}",
            "event": "INCUR_PENALTY_FEES",
        }

        common_args = (
            dict(
                amount=amount,
                client_transaction_id="MOCK_HOOK_CHARGE_FEE",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )

        return [
            self.mock_posting_instruction(
                account_id=loc_account_id,
                address=address.PENALTIES,
                credit=False,
                **common_args,
            ),
            self.mock_posting_instruction(
                account_id="late_repayment_fee_income_account",
                address=address.DEFAULT,
                credit=True,
                **common_args,
            ),
        ]

    def expected_accrual_postings(
        self,
        account_id: str,
        amount: Decimal,
        effective_balance: Optional[Decimal] = None,
        instruction_details: Optional[dict[str, str]] = None,
        client_transaction_id_prefix: str = "ACCRUE_INTEREST",
        reverse: bool = False,
    ) -> list[PostingInstruction]:

        instruction_details = instruction_details or {
            "description": f"Daily interest accrued on balance of {effective_balance}",
            "event": interest_accrual.ACCRUAL_EVENT,
        }
        common_args = (
            dict(
                account_id=account_id,
                amount=amount,
                client_transaction_id=client_transaction_id_prefix + "_MOCK_HOOK_"
                f"{self.default_denom}",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )

        return (
            [
                self.mock_posting_instruction(
                    address=interest_accrual.INTERNAL_CONTRA, credit=False, **common_args
                ),
                self.mock_posting_instruction(
                    address=interest_accrual.ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    credit=True,
                    **common_args,
                ),
            ]
            if reverse
            else [
                self.mock_posting_instruction(
                    address=interest_accrual.ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
                    credit=False,
                    **common_args,
                ),
                self.mock_posting_instruction(
                    address=interest_accrual.INTERNAL_CONTRA, credit=True, **common_args
                ),
            ]
        )

    def expected_application_postings(
        self,
        account_id: str,
        apply_amount: Decimal,
        accrue_amount: Decimal,
        instruction_details: Optional[dict[str, str]] = None,
        client_transaction_id_prefix="APPLY_ACCRUED_INTEREST",
    ) -> list[PostingInstruction]:
        # Only handling one rounding direction for simplicity

        instruction_details = instruction_details or {
            "description": "Interest Applied",
            "event": interest_application.APPLICATION_EVENT,
        }

        common_args_internal = (
            dict(
                amount=apply_amount,
                client_transaction_id=client_transaction_id_prefix + "_MOCK_HOOK_"
                f"{self.default_denom}_INTERNAL",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )

        # contra_credit = False if reverse else True
        # interest_credit = True if reverse else False

        # internal account and customer postings for both apply and clearing residual interest
        # (round up)
        return [
            # Internal account application postings
            self.mock_posting_instruction(
                account_id=account_id,
                address=interest_application.INTEREST_DUE,
                credit=False,
                **common_args_internal,
            ),
            self.mock_posting_instruction(
                account_id="accrued_interest_receivable",
                address=DEFAULT_ADDRESS,
                credit=True,
                **common_args_internal,
            ),
            # Clearing Residual interest postings
            *self.expected_accrual_postings(
                account_id=account_id,
                amount=accrue_amount,
                instruction_details={
                    "description": "Zeroing remainder accrued interest after application",
                    "event": interest_application.APPLICATION_EVENT,
                },
                client_transaction_id_prefix="REVERSE_RESIDUAL_ACCRUED_INTEREST_RECEIVABLE",
                reverse=True,
            ),
        ]

    def expected_overpayment_accrual_postings(
        self,
        account_id: str,
        amount: Decimal,
        effective_balance: Optional[Decimal] = None,
    ) -> list[PostingInstruction]:
        instruction_details = {
            "description": f"Daily interest excluding overpayment effects accrued on balance of "
            f"{effective_balance}"
        }
        common_args = (
            dict(
                account_id=account_id,
                amount=amount,
                client_transaction_id="UPDATE_ACCRUED_EXPECTED_INTEREST_MOCK_HOOK",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )

        return [
            self.mock_posting_instruction(
                address=overpayment.ACCRUED_EXPECTED_INTEREST, credit=False, **common_args
            ),
            self.mock_posting_instruction(
                address=interest_accrual.INTERNAL_CONTRA, credit=True, **common_args
            ),
        ]

    def expected_overpayment_application_postings(
        self,
        account_id: str,
        amount: Decimal,
    ) -> list[PostingInstruction]:
        instruction_details = {"description": f"Clear {overpayment.ACCRUED_EXPECTED_INTEREST}"}
        common_args = (
            dict(
                account_id=account_id,
                amount=amount,
                client_transaction_id="UPDATE_ACCRUED_EXPECTED_INTEREST_MOCK_HOOK",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )

        return [
            self.mock_posting_instruction(
                address=interest_accrual.INTERNAL_CONTRA, credit=False, **common_args
            ),
            self.mock_posting_instruction(
                address=overpayment.ACCRUED_EXPECTED_INTEREST, credit=True, **common_args
            ),
        ]

    def expected_emi_postings(
        self,
        account_id: str,
        old_emi: Decimal,
        new_emi: Decimal,
    ) -> list[PostingInstruction]:
        instruction_details = {
            "description": f"Updating EMI amount from {old_emi} to {new_emi}",
            "event": debt_management.DUE_AMOUNT_CALCULATION,
        }

        common_args = (
            dict(
                account_id=account_id,
                amount=abs(new_emi - old_emi),
                client_transaction_id=f"UPDATE_EMI_{self.hook_execution_id}",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )

        if old_emi > new_emi:
            return [
                self.mock_posting_instruction(
                    address=debt_management.INTERNAL_CONTRA, credit=False, **common_args
                ),
                self.mock_posting_instruction(
                    address=debt_management.EMI_ADDRESS, credit=True, **common_args
                ),
            ]
        else:
            return [
                self.mock_posting_instruction(
                    address=debt_management.INTERNAL_CONTRA, credit=True, **common_args
                ),
                self.mock_posting_instruction(
                    address=debt_management.EMI_ADDRESS, credit=False, **common_args
                ),
            ]

    def expected_emi_excess_postings(
        self,
        account_id: str,
        amount: Decimal,
    ) -> list[PostingInstruction]:

        instruction_details = {
            "description": f"Increase {overpayment.EMI_PRINCIPAL_EXCESS} by {amount}"
        }

        common_args = (
            dict(
                account_id=account_id,
                amount=amount,
                client_transaction_id=f"UPDATE_{overpayment.EMI_PRINCIPAL_EXCESS}_"
                f"{self.hook_execution_id}",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )

        return [
            self.mock_posting_instruction(
                address=overpayment.EMI_PRINCIPAL_EXCESS, credit=False, **common_args
            ),
            self.mock_posting_instruction(
                address=debt_management.INTERNAL_CONTRA, credit=True, **common_args
            ),
        ]

    def expected_principal_due_postings(
        self,
        account_id: str,
        amount: Decimal,
    ) -> list[PostingInstruction]:
        # Decrease only, as we don't need multiple scenarios in these tests

        instruction_details = {
            "description": f"Monthly principal added to due address: {amount}",
            "event": debt_management.DUE_AMOUNT_CALCULATION,
        }

        common_args = (
            dict(
                account_id=account_id,
                amount=amount,
                client_transaction_id=f"UPDATE_PRINCIPAL_DUE_{self.hook_execution_id}",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )

        return [
            self.mock_posting_instruction(
                address=debt_management.PRINCIPAL_DUE_ADDRESS, credit=False, **common_args
            ),
            self.mock_posting_instruction(
                address=disbursement.PRINCIPAL, credit=True, **common_args
            ),
        ]

    def expected_principal_overdue_postings(
        self,
        account_id: str,
        amount: Decimal,
    ) -> list[PostingInstruction]:
        # Decrease only, as we don't need multiple scenarios in these tests

        instruction_details = {
            "description": f"Mark outstanding due amount of {amount} as PRINCIPAL_OVERDUE.",
            "event": "MOVE_BALANCE_INTO_PRINCIPAL_OVERDUE",
        }

        common_args = (
            dict(
                account_id=account_id,
                amount=amount,
                client_transaction_id=f"{self.hook_execution_id}_PRINCIPAL_OVERDUE",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )

        return [
            self.mock_posting_instruction(
                address=debt_management.PRINCIPAL_OVERDUE_ADDRESS, credit=False, **common_args
            ),
            self.mock_posting_instruction(
                address=debt_management.PRINCIPAL_DUE_ADDRESS, credit=True, **common_args
            ),
        ]

    def expected_interest_overdue_postings(
        self,
        account_id: str,
        amount: Decimal,
    ) -> list[PostingInstruction]:
        # Decrease only, as we don't need multiple scenarios in these tests

        instruction_details = {
            "description": f"Mark outstanding due amount of {amount} as INTEREST_OVERDUE.",
            "event": "MOVE_BALANCE_INTO_INTEREST_OVERDUE",
        }

        common_args = (
            dict(
                account_id=account_id,
                amount=amount,
                client_transaction_id=f"{self.hook_execution_id}_INTEREST_OVERDUE",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )

        return [
            self.mock_posting_instruction(
                address=debt_management.INTEREST_OVERDUE_ADDRESS, credit=False, **common_args
            ),
            self.mock_posting_instruction(
                address=debt_management.INTEREST_DUE_ADDRESS, credit=True, **common_args
            ),
        ]

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
        common_args = (
            dict(
                account_id=account_id,
                amount=amount,
                client_transaction_id=f"AGGREGATE_{aggregate_address}_{self.hook_execution_id}",
                instruction_details=instruction_details,
            )
            | self.COMMON_POSTING_ARGS
        )

        if credit_aggregate_address:
            return [
                self.mock_posting_instruction(
                    address=interest_accrual.INTERNAL_CONTRA, credit=False, **common_args
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
                    address=interest_accrual.INTERNAL_CONTRA, credit=True, **common_args
                ),
            ]


class PrePostingTest(LOCTest):
    def setUp(self):
        # The total due amount per loan is 2 * (50+10)  = 120
        # penalties (counts as due) = 20.12
        # undue principal is 2 * 100  = 200
        # max overpayment fee is 200 * 0.05 = 10
        # undue interest is 2 * round(10.12345, 2) = 20.24
        # full early repayment amount = 370.36
        loan_balances = self.balances_for_loan_account(
            principal_due=Decimal("50"),
            interest_due=Decimal("10"),
            principal=Decimal("100"),
            accrued_interest_receivable=Decimal("10.12345"),
        )
        loc_balances = self.balances_for_loc_account(
            penalties=Decimal("20.12"),
        )
        loan_balance_observation_fetcher_mapping = {
            "live_balances": BalancesObservation(balances=loan_balances[0][1])
        }

        loc_balance_observation_fetcher_mapping = {
            "live_balances": BalancesObservation(balances=loc_balances[0][1])
        }

        self.vault, _, _, _ = self.get_default_setup_with_observation_fetchers(
            loan_1_balances_observation_fetchers_mapping=loan_balance_observation_fetcher_mapping,
            loan_2_balances_observation_fetchers_mapping=loan_balance_observation_fetcher_mapping,
            loc_balances_observation_fetchers_mapping=loc_balance_observation_fetcher_mapping,
        )
        return super().setUp()

    def test_override_posting_always_accepted(self):
        # should get rejected if not for the batch_details
        postings = PostingInstructionBatch(
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("5"))]
        )
        postings_with_override = PostingInstructionBatch(
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("5"))],
            batch_details={"force_override": "true"},
        )
        # running with and without batch_details to ensure it is just the batch_details preventing
        # the rejection
        with self.assertRaises(Rejected):
            self.run_function(
                "pre_posting_code",
                self.create_supervisor_mock(),
                postings=postings,
                effective_date=DEFAULT_DATE,
            )
        self.assertIsNone(
            self.run_function(
                "pre_posting_code",
                self.create_supervisor_mock(),
                postings=postings_with_override,
                effective_date=DEFAULT_DATE,
            )
        )

    def test_supervisee_rejection_causes_supervisor_rejection(self):
        postings = PostingInstructionBatch(
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("5"))]
        )
        mock_loc = self.create_default_loc_supervisee_mock()
        mock_loc.get_hook_return_data.return_value = Rejected(
            message="Supervisee Rejection", reason_code=RejectedReason.CLIENT_CUSTOM_REASON
        )

        self.vault.supervisees.update({DEFAULT_LOC_ACCOUNT_ID: mock_loc})

        with self.assertRaises(Rejected) as ctx:
            self.run_function(
                "pre_posting_code",
                self.vault,
                postings=postings,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            ctx.exception.message,
            "Supervisee Rejection",
        )

    def test_plan_with_no_associated_loc_rejects_postings(self):
        postings = PostingInstructionBatch(
            posting_instructions=[self.inbound_hard_settlement(amount=Decimal("5"))]
        )
        with self.assertRaises(Rejected) as ctx:
            self.run_function(
                "pre_posting_code",
                self.create_supervisor_mock(),
                postings=postings,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            ctx.exception.message,
            "Cannot process postings until a line_of_credit account is associated to the plan",
        )

    def test_repayment_at_due_amounts_accepted(self):
        postings = PostingInstructionBatch(
            posting_instructions=[self.inbound_hard_settlement(Decimal("140.12"))]
        )

        self.assertIsNone(self.run_function("pre_posting_code", self.vault, postings, DEFAULT_DATE))

    def test_repayment_below_due_amounts_accepted(self):
        postings = PostingInstructionBatch(
            posting_instructions=[self.inbound_hard_settlement(Decimal("100"))]
        )

        self.assertIsNone(self.run_function("pre_posting_code", self.vault, postings, DEFAULT_DATE))

    def test_overpayment_to_principal_only_accepted(self):

        postings = PostingInstructionBatch(
            posting_instructions=[self.inbound_hard_settlement(Decimal("200"))]
        )

        self.assertIsNone(self.run_function("pre_posting_code", self.vault, postings, DEFAULT_DATE))

    def test_full_early_overpayment_accepted(self):
        postings = PostingInstructionBatch(
            posting_instructions=[self.inbound_hard_settlement(Decimal("370.36"))]
        )

        self.assertIsNone(self.run_function("pre_posting_code", self.vault, postings, DEFAULT_DATE))

    def test_repayment_above_full_early_repayment_rejected(self):
        postings = PostingInstructionBatch(
            posting_instructions=[self.inbound_hard_settlement(Decimal("370.37"))]
        )

        with self.assertRaises(Rejected) as ctx:
            self.run_function("pre_posting_code", self.vault, postings, DEFAULT_DATE)

        self.assertEqual(
            ctx.exception.message,
            "Repayment amount 370.37 exceeds total outstanding + overpayment fees 370.36",
        )

    def test_repayment_with_no_outstanding_amounts_rejected(self):
        loan_balances = self.balances_for_loan_account(
            principal_overdue=Decimal("0"),
            interest_overdue=Decimal("0"),
            principal_due=Decimal("0"),
            interest_due=Decimal("0"),
            principal=Decimal("0"),
            accrued_interest_receivable=Decimal("0"),
        )
        loc_balances = self.balances_for_loc_account(
            penalties=Decimal("0"),
        )

        loan_balance_observation_fetcher_mapping = {
            "live_balances": BalancesObservation(balances=loan_balances[0][1])
        }
        loc_balance_observation_fetcher_mapping = {
            "live_balances": BalancesObservation(balances=loc_balances[0][1])
        }

        vault, _, _, _ = self.get_default_setup_with_observation_fetchers(
            loan_1_balances_observation_fetchers_mapping=loan_balance_observation_fetcher_mapping,
            loan_2_balances_observation_fetchers_mapping=loan_balance_observation_fetcher_mapping,
            loc_balances_observation_fetchers_mapping=loc_balance_observation_fetcher_mapping,
        )

        postings = PostingInstructionBatch(
            posting_instructions=[self.inbound_hard_settlement(Decimal("100"))]
        )
        with self.assertRaises(Rejected) as ctx:
            self.run_function("pre_posting_code", vault, postings, DEFAULT_DATE)

        self.assertEqual(
            ctx.exception.message,
            "There are no more repayments/overpayments to be made against this line of credit",
        )

    def test_targeted_repayment_triggers_rejection_if_nothing_to_pay(self):
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("150"),
                    instruction_details={
                        "target_account_id": DEFAULT_LOAN_2_ACCOUNT_ID,
                    },
                )
            ]
        )

        loan_1_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_due=Decimal("100"),
            principal=Decimal("50"),
        )
        loan_2_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_due=Decimal("0"),
            principal=Decimal("0"),
        )
        loc_balances = self.balances_for_loc_account(
            penalties=Decimal("0"),
        )
        loan_1_balance_observation_fetcher_mapping = {
            "live_balances": BalancesObservation(balances=loan_1_balance_ts[0][1])
        }
        loan_2_balance_observation_fetcher_mapping = {
            "live_balances": BalancesObservation(balances=loan_2_balance_ts[0][1])
        }
        loc_balance_observation_fetcher_mapping = {
            "live_balances": BalancesObservation(balances=loc_balances[0][1])
        }
        mock_vault, _, _, _ = self.get_default_setup_with_observation_fetchers(
            loan_1_balances_observation_fetchers_mapping=loan_1_balance_observation_fetcher_mapping,
            loan_2_balances_observation_fetchers_mapping=loan_2_balance_observation_fetcher_mapping,
            loc_balances_observation_fetchers_mapping=loc_balance_observation_fetcher_mapping,
        )

        with self.assertRaises(Rejected) as ctx:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=postings,
                effective_date=DEFAULT_DATE,
            )

        self.assertEqual(
            ctx.exception.message,
            "There are no more repayments/overpayments to be made against this line of credit",
        )

    def test_targeted_repayment_accepted(self):
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("10"),
                    instruction_details={
                        "target_account_id": DEFAULT_LOAN_2_ACCOUNT_ID,
                    },
                )
            ]
        )

        loan_1_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_due=Decimal("0"),
            principal=Decimal("0"),
        )
        loan_2_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_due=Decimal("100"),
            principal=Decimal("50"),
        )
        loc_balances = self.balances_for_loc_account(
            penalties=Decimal("0"),
        )
        loan_1_balance_observation_fetcher_mapping = {
            "live_balances": BalancesObservation(balances=loan_1_balance_ts[0][1])
        }
        loan_2_balance_observation_fetcher_mapping = {
            "live_balances": BalancesObservation(balances=loan_2_balance_ts[0][1])
        }
        loc_balance_observation_fetcher_mapping = {
            "live_balances": BalancesObservation(balances=loc_balances[0][1])
        }
        mock_vault, _, _, _ = self.get_default_setup_with_observation_fetchers(
            loan_1_balances_observation_fetchers_mapping=loan_1_balance_observation_fetcher_mapping,
            loan_2_balances_observation_fetchers_mapping=loan_2_balance_observation_fetcher_mapping,
            loc_balances_observation_fetchers_mapping=loc_balance_observation_fetcher_mapping,
        )

        self.assertIsNone(self.run_function("pre_posting_code", mock_vault, postings, DEFAULT_DATE))


class PostPostingTest(LOCTest):
    def test_repayment_postings_when_owed_equals_repayment(self):
        loan_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_overdue=Decimal("100"),
        )

        _, mock_loan_1, mock_loan_2, mock_loc, = self.get_default_setup(
            loan_1_balance_ts=loan_balance_ts,
            loan_2_balance_ts=loan_balance_ts,
        )

        mock_loans = [mock_loan_1, mock_loan_2]

        supervisor._process_repayment(
            supervisees=mock_loans,
            repayment_amount=Decimal(200),
            denomination=DEFAULT_DENOMINATION,
            repayment_hierarchy=self.REPAYMENT_HIERARCHY,
        )

        mock_loan_1.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal(100),
            denomination=DEFAULT_DENOMINATION,
            client_transaction_id="PRINCIPAL_OVERDUE_REPAYMENT_FROM_loan_1_MOCK_HOOK",
            from_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            from_account_address=address.INTERNAL_CONTRA,
            to_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            to_account_address=address.PRINCIPAL_OVERDUE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Repayment of address: PRINCIPAL_OVERDUE for loan loan_1",
                "event": "REPAYMENT",
            },
        )
        mock_loan_2.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal(100),
            denomination=DEFAULT_DENOMINATION,
            client_transaction_id="PRINCIPAL_OVERDUE_REPAYMENT_FROM_loan_2_MOCK_HOOK",
            from_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            from_account_address=address.INTERNAL_CONTRA,
            to_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            to_account_address=address.PRINCIPAL_OVERDUE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Repayment of address: PRINCIPAL_OVERDUE for loan loan_2",
                "event": "REPAYMENT",
            },
        )

    def test_repayment_postings_with_penalties_on_loc(self):
        loan_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_overdue=Decimal("100"),
        )
        loc_balance_ts = self.balances_for_loan_account(penalties=Decimal("100"))

        _, mock_loan_1, mock_loan_2, _, = self.get_default_setup(
            loan_1_balance_ts=loan_balance_ts,
            loan_2_balance_ts=loan_balance_ts,
            loc_balance_ts=loc_balance_ts,
        )
        mock_loc = self.create_default_loc_supervisee_mock(balance_ts=loc_balance_ts)
        mock_supervisees = [mock_loan_1, mock_loan_2, mock_loc]

        supervisor._process_repayment(
            supervisees=mock_supervisees,
            repayment_hierarchy=repayment_hierarchies.REPAYMENT_HIERARCHY,
            repayment_amount=Decimal(250),
            denomination=DEFAULT_DENOMINATION,
        )

        mock_loan_1.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal(100),
            denomination=DEFAULT_DENOMINATION,
            client_transaction_id="PRINCIPAL_OVERDUE_REPAYMENT_FROM_loan_1_MOCK_HOOK",
            from_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            from_account_address=address.INTERNAL_CONTRA,
            to_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            to_account_address=address.PRINCIPAL_OVERDUE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Repayment of address: PRINCIPAL_OVERDUE for loan loan_1",
                "event": "REPAYMENT",
            },
        )
        mock_loan_2.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal(100),
            denomination=DEFAULT_DENOMINATION,
            client_transaction_id="PRINCIPAL_OVERDUE_REPAYMENT_FROM_loan_2_MOCK_HOOK",
            from_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            from_account_address=address.INTERNAL_CONTRA,
            to_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            to_account_address=address.PRINCIPAL_OVERDUE,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Repayment of address: PRINCIPAL_OVERDUE for loan loan_2",
                "event": "REPAYMENT",
            },
        )
        mock_loc.make_internal_transfer_instructions.assert_called_once_with(
            amount=Decimal(50),
            denomination=DEFAULT_DENOMINATION,
            client_transaction_id="PENALTIES_REPAYMENT_FROM_loc_MOCK_HOOK",
            from_account_id=DEFAULT_LOC_ACCOUNT_ID,
            from_account_address=address.DEFAULT,
            to_account_id=DEFAULT_LOC_ACCOUNT_ID,
            to_account_address=address.PENALTIES,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            instruction_details={
                "description": "Repayment of address: PENALTIES for loan loc",
                "event": "REPAYMENT",
            },
        )

    def test_repayment_postings_when_owed_is_more_than_repayment(self):
        loan_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_due=Decimal("100"),
        )

        _, mock_loan_1, mock_loan_2, _, = self.get_default_setup(
            loan_1_balance_ts=loan_balance_ts,
            loan_2_balance_ts=loan_balance_ts,
        )

        mock_loans = [mock_loan_1, mock_loan_2]

        supervisor._process_repayment(
            supervisees=mock_loans,
            repayment_hierarchy=repayment_hierarchies.REPAYMENT_HIERARCHY,
            repayment_amount=Decimal(50),
            denomination=DEFAULT_DENOMINATION,
        )

        mock_loan_1.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal(50),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="PRINCIPAL_DUE_REPAYMENT_FROM_loan_1_MOCK_HOOK",
                    from_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                    from_account_address=address.INTERNAL_CONTRA,
                    to_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                    to_account_address=address.PRINCIPAL_DUE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Repayment of address: PRINCIPAL_DUE for loan loan_1",
                        "event": "REPAYMENT",
                    },
                ),
            ]
        )

    def test_postings_per_loan_structure(self):
        loan_1_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_overdue=Decimal("100"),
            interest_overdue=Decimal("10"),
            principal=Decimal("0"),
        )
        loan_2_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_overdue=Decimal("50"),
            interest_overdue=Decimal("5"),
            principal=Decimal("0"),
        )

        _, mock_loan_1, mock_loan_2, mock_loc, = self.get_default_setup(
            loan_1_balance_ts=loan_1_balance_ts,
            loan_2_balance_ts=loan_2_balance_ts,
        )

        expected_postings_principal_loan_1 = self.expected_repayment_postings(
            loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            repayment_address=address.PRINCIPAL_OVERDUE,
            amount=Decimal("100"),
        )
        expected_postings_interest_loan_1 = self.expected_repayment_postings(
            loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            repayment_address=address.INTEREST_OVERDUE,
            amount=Decimal("10"),
        )

        expected_postings_principal_loan_2 = self.expected_repayment_postings(
            loan_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            repayment_address=address.PRINCIPAL_OVERDUE,
            amount=Decimal("50"),
        )
        expected_postings_interest_loan_2 = self.expected_repayment_postings(
            loan_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            repayment_address=address.INTEREST_OVERDUE,
            amount=Decimal("5"),
        )

        expected_postings_per_loan = {
            mock_loan_1: [],
            mock_loan_2: [],
        }
        expected_postings_per_loan[mock_loan_1].extend(expected_postings_principal_loan_1)
        expected_postings_per_loan[mock_loan_1].extend(expected_postings_interest_loan_1)
        expected_postings_per_loan[mock_loan_2].extend(expected_postings_principal_loan_2)
        expected_postings_per_loan[mock_loan_2].extend(expected_postings_interest_loan_2)

        mock_loans = [mock_loan_1, mock_loan_2]

        (postings_per_loan, _) = supervisor._process_repayment(
            supervisees=mock_loans,
            repayment_hierarchy=repayment_hierarchies.REPAYMENT_HIERARCHY,
            repayment_amount=Decimal(500),
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(postings_per_loan, expected_postings_per_loan)

    def test_repayment_postings_are_ordered_correctly(self):
        # here we have 3 repayment addresses over two loans that should have
        # the following order:
        # LOAN 1 - OVERDUE PRINCIPAL - 1000
        # LOAN 2 - OVERDUE PRINCIPAL - 2000
        # LOAN 1 - PRINCIPAL         - 100
        # LOAN 1 - ACCRUED INTEREST  - 10
        # LOAN 2 - PRINCIPAL         - 200
        # LOAN 2 - ACCRUED INTEREST  - 20
        loan_1_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_overdue=Decimal("1000"),
            accrued_interest_receivable=Decimal("10"),
            principal=Decimal("100"),
        )
        loan_2_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_overdue=Decimal("2000"),
            accrued_interest_receivable=Decimal("20"),
            principal=Decimal("200"),
        )

        _, mock_loan_1, mock_loan_2, mock_loc, = self.get_default_setup(
            loan_1_balance_ts=loan_1_balance_ts,
            loan_2_balance_ts=loan_2_balance_ts,
        )

        mock_loans = [mock_loan_1, mock_loan_2]

        supervisor._process_repayment(
            supervisees=mock_loans,
            repayment_amount=Decimal(5000),
            denomination=DEFAULT_DENOMINATION,
            repayment_hierarchy=self.EARLY_REPAYMENT_HIERARCHY,
        )

        mock_loan_1.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal(1000),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="PRINCIPAL_OVERDUE_REPAYMENT_FROM_loan_1_MOCK_HOOK",
                    from_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                    from_account_address=address.INTERNAL_CONTRA,
                    to_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                    to_account_address=address.PRINCIPAL_OVERDUE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Repayment of address: PRINCIPAL_OVERDUE for loan loan_1",
                        "event": "REPAYMENT",
                    },
                ),
                call(
                    amount=Decimal(100),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="PRINCIPAL_REPAYMENT_FROM_loan_1_MOCK_HOOK",
                    from_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                    # Principal is repaid from overpayment
                    from_account_address=address.OVERPAYMENT,
                    to_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                    to_account_address=address.PRINCIPAL,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Repayment of address: PRINCIPAL for loan loan_1",
                        "event": "REPAYMENT",
                    },
                ),
                call(
                    amount=Decimal(1),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="TRACK_OVERPAYMENT_MOCK_HOOK",
                    from_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                    from_account_address=address.OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC,
                    to_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                    to_account_address=address.INTERNAL_CONTRA,
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal(10),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="ACCRUED_INTEREST_RECEIVABLE_REPAYMENT_"
                    "FROM_loan_1_MOCK_HOOK",
                    from_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                    from_account_address=address.INTERNAL_CONTRA,
                    to_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                    to_account_address=address.ACCRUED_INTEREST_RECEIVABLE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Repayment of address: ACCRUED_INTEREST_RECEIVABLE for "
                        + "loan loan_1",
                        "event": "REPAYMENT",
                    },
                ),
            ]
        )
        mock_loan_2.make_internal_transfer_instructions.assert_has_calls(
            [
                call(
                    amount=Decimal(2000),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="PRINCIPAL_OVERDUE_REPAYMENT_FROM_loan_2_MOCK_HOOK",
                    from_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
                    from_account_address=address.INTERNAL_CONTRA,
                    to_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
                    to_account_address=address.PRINCIPAL_OVERDUE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Repayment of address: PRINCIPAL_OVERDUE for loan loan_2",
                        "event": "REPAYMENT",
                    },
                ),
                call(
                    amount=Decimal(200),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="PRINCIPAL_REPAYMENT_FROM_loan_2_MOCK_HOOK",
                    from_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
                    # Principal is repaid from overpayment
                    from_account_address=address.OVERPAYMENT,
                    to_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
                    to_account_address=address.PRINCIPAL,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Repayment of address: PRINCIPAL for loan loan_2",
                        "event": "REPAYMENT",
                    },
                ),
                call(
                    amount=Decimal(1),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="TRACK_OVERPAYMENT_MOCK_HOOK",
                    from_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
                    from_account_address=address.OVERPAYMENTS_SINCE_LAST_DUE_AMOUNT_CALC,
                    to_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
                    to_account_address=address.INTERNAL_CONTRA,
                    override_all_restrictions=True,
                ),
                call(
                    amount=Decimal(20),
                    denomination=DEFAULT_DENOMINATION,
                    client_transaction_id="ACCRUED_INTEREST_RECEIVABLE_REPAYMENT_"
                    "FROM_loan_2_MOCK_HOOK",
                    from_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
                    from_account_address=address.INTERNAL_CONTRA,
                    to_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
                    to_account_address=address.ACCRUED_INTEREST_RECEIVABLE,
                    asset=DEFAULT_ASSET,
                    override_all_restrictions=True,
                    instruction_details={
                        "description": "Repayment of address: ACCRUED_INTEREST_RECEIVABLE for "
                        + "loan loan_2",
                        "event": "REPAYMENT",
                    },
                ),
            ]
        )

    def test_pibs_are_instructed_from_postings_per_loan(self):
        loan_1_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE, principal_overdue=Decimal("100"), principal=Decimal("10")
        )
        loan_2_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE, principal_overdue=Decimal("200"), principal=Decimal("20")
        )

        mock_vault, mock_loan_1, mock_loan_2, mock_loc, = self.get_default_setup(
            loan_1_balance_ts=loan_1_balance_ts,
            loan_2_balance_ts=loan_2_balance_ts,
        )

        postings_per_loan = {
            mock_loan_1: [],
            mock_loan_2: [],
        }

        principal_overdue_loan_1 = self.expected_repayment_postings(
            loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            repayment_address=address.PRINCIPAL_OVERDUE,
            amount=Decimal("100"),
        )
        principal_loan_1 = self.expected_repayment_postings(
            loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            repayment_address=address.PRINCIPAL,
            amount=Decimal("10"),
        )
        principal_overdue_loan_2 = self.expected_repayment_postings(
            loan_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            repayment_address=address.PRINCIPAL_OVERDUE,
            amount=Decimal("200"),
        )
        principal_loan_2 = self.expected_repayment_postings(
            loan_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            repayment_address=address.PRINCIPAL,
            amount=Decimal("20"),
        )

        postings_per_loan[mock_loan_1].extend(principal_overdue_loan_1)
        postings_per_loan[mock_loan_1].extend(principal_loan_1)
        postings_per_loan[mock_loan_2].extend(principal_overdue_loan_2)
        postings_per_loan[mock_loan_2].extend(principal_loan_2)

        supervisor._instruct_loan_repayment_pib(postings_per_loan, DEFAULT_DATE)
        mock_loan_1.instruct_posting_batch.assert_called_once_with(
            posting_instructions=postings_per_loan[mock_loan_1],
            effective_date=DEFAULT_DATE,
            client_batch_id=f"REPAYMENT_{mock_loan_1.account_id}_MOCK_HOOK",
            batch_details={"force_override": "true"},
        )
        mock_loan_2.instruct_posting_batch.assert_called_once_with(
            posting_instructions=postings_per_loan[mock_loan_2],
            effective_date=DEFAULT_DATE,
            client_batch_id=f"REPAYMENT_{mock_loan_2.account_id}_MOCK_HOOK",
            batch_details={"force_override": "true"},
        )

    def test_regular_repayment_logic_is_triggered(self):
        loan_1_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_due=Decimal("100"),
        )
        (
            mock_vault,
            mock_loan_1,
            _,
            _,
        ) = self.get_default_setup(loan_1_balance_ts=loan_1_balance_ts)
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("100"),
                    instruction_details={
                        "description": "Repayment from a customer",
                        "event": "INCOMING_REPAYMENT",
                    },
                )
            ]
        )
        self.run_function("post_posting_code", mock_vault, postings, DEFAULT_DATE)

        expected_postings = self.expected_repayment_postings(
            loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            repayment_address=address.PRINCIPAL_DUE,
            amount=Decimal("100"),
        )

        mock_loan_1.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_postings,
            effective_date=DEFAULT_DATE,
            client_batch_id=f"REPAYMENT_{mock_loan_1.account_id}_MOCK_HOOK",
            batch_details={"force_override": "true"},
        )

    def test_regular_and_overpayment_repayment_logic_is_triggered(self):
        loan_1_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_due=Decimal("100"),
            principal=Decimal("50"),
        )
        mock_vault, mock_loan_1, _, _ = self.get_default_setup(loan_1_balance_ts=loan_1_balance_ts)
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("150"),
                    instruction_details={
                        "description": "Repayment from a customer",
                        "event": "INCOMING_REPAYMENT",
                    },
                )
            ]
        )
        self.run_function("post_posting_code", mock_vault, postings, DEFAULT_DATE)

        expected_postings = [
            *self.expected_repayment_postings(
                loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                repayment_address=address.PRINCIPAL_DUE,
                amount=Decimal("100"),
            ),
            *self.expected_repayment_postings(
                loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                repayment_address=address.PRINCIPAL,
                repayment_from_address=address.OVERPAYMENT,
                # 2.5 deducted for overpayment fee
                amount=Decimal("47.5"),
            ),
            *self.expected_overpayment_tracker_postings(loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID),
        ]

        mock_loan_1.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_postings,
            effective_date=DEFAULT_DATE,
            client_batch_id=f"REPAYMENT_{mock_loan_1.account_id}_MOCK_HOOK",
            batch_details={"force_override": "true"},
        )

    def test_overpayment_fee_charged_for_overpayment(self):
        loan_1_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_due=Decimal("100"),
            principal=Decimal("50"),
        )
        mock_vault, mock_loan_1, _, mock_loc = self.get_default_setup(
            loan_1_balance_ts=loan_1_balance_ts
        )
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("150"),
                    instruction_details={
                        "description": "Repayment from a customer",
                        "event": "INCOMING_REPAYMENT",
                    },
                )
            ]
        )
        self.run_function("post_posting_code", mock_vault, postings, DEFAULT_DATE)

        expected_postings = [
            *self.expected_repayment_postings(
                loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                repayment_address=address.PRINCIPAL_DUE,
                amount=Decimal("100"),
            ),
            *self.expected_repayment_postings(
                loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                repayment_address=address.PRINCIPAL,
                repayment_from_address=address.OVERPAYMENT,
                # 2.5 fee is deducted for overpayment
                amount=Decimal("47.5"),
            ),
            *self.expected_overpayment_tracker_postings(loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID),
        ]

        expected_loc_postings = [
            *self.expected_overpayment_fee_postings(amount=Decimal("2.50")),
        ]

        mock_loan_1.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_postings,
            effective_date=DEFAULT_DATE,
            client_batch_id=f"REPAYMENT_{mock_loan_1.account_id}_MOCK_HOOK",
            batch_details={"force_override": "true"},
        )

        mock_loc.instruct_posting_batch.assert_has_calls(
            [
                call(
                    posting_instructions=expected_loc_postings,
                    effective_date=DEFAULT_DATE,
                    client_batch_id=f"REPAYMENT_{mock_loc.account_id}_MOCK_HOOK",
                    batch_details={"force_override": "true"},
                ),
                call(
                    posting_instructions=ANY,
                    effective_date=DEFAULT_DATE,
                    client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
                    batch_details={"force_override": "True"},
                ),
            ]
        )

    def test_overpayment_fee_not_charged_for_zero_overpayment_fee_rate(self):
        loan_1_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_due=Decimal("100"),
            principal=Decimal("50"),
        )
        mock_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            balance_ts=loan_1_balance_ts,
            make_instructions_return_full_objects=True,
        )
        mock_loc = self.create_default_loc_supervisee_mock(overpayment_fee_percentage=Decimal("0"))
        mock_vault = self.create_supervisor_mock(
            supervisees={
                DEFAULT_LOAN_1_ACCOUNT_ID: mock_loan_1,
                DEFAULT_LOC_ACCOUNT_ID: mock_loc,
            }
        )
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("150"),
                    instruction_details={
                        "description": "Repayment from a customer",
                        "event": "INCOMING_REPAYMENT",
                    },
                )
            ]
        )

        self.run_function("post_posting_code", mock_vault, postings, DEFAULT_DATE)

        expected_postings = [
            *self.expected_repayment_postings(
                loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                repayment_address=address.PRINCIPAL_DUE,
                amount=Decimal("100"),
            ),
            *self.expected_repayment_postings(
                loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                repayment_address=address.PRINCIPAL,
                repayment_from_address=address.OVERPAYMENT,
                amount=Decimal("50"),
            ),
            *self.expected_overpayment_tracker_postings(loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID),
        ]

        mock_loan_1.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_postings,
            effective_date=DEFAULT_DATE,
            client_batch_id=f"REPAYMENT_{mock_loan_1.account_id}_MOCK_HOOK",
            batch_details={"force_override": "true"},
        )

        mock_loc.instruct_posting_batch.assert_called_once_with(
            posting_instructions=ANY,
            effective_date=DEFAULT_DATE,
            client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
            batch_details={"force_override": "True"},
        )

    def test_repayment_amounts_rounded_individually(self):
        # Total due is 200, not due principal 100 and not due interest 0.24
        loan_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_due=Decimal("100"),
            principal=Decimal("50"),
            # rounds to 0.12, but if rounded after summing would round to 0.25
            accrued_interest_receivable=Decimal("0.123"),
        )

        mock_vault, mock_loan_1, mock_loan_2, mock_loc = self.get_default_setup(
            loan_1_balance_ts=loan_balance_ts, loan_2_balance_ts=loan_balance_ts
        )
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("300.24"),
                    instruction_details={
                        "description": "Repayment from a customer",
                        "event": "INCOMING_REPAYMENT",
                    },
                )
            ]
        )

        self.run_function("post_posting_code", mock_vault, postings, DEFAULT_DATE)

        # 300.24 should be spread as follows
        # - 200 principal due across both loans
        # - 100*0.05 = 5 to fee as there is 100 principal
        # - 50 principal on loan 1 (overpayment)
        # - 0.12 accrued interest on loan 1
        # - 45.12 principal on loan 2 (overpayment)
        # No repayment of loan 2 accrued interest as its principal was not fully paid off
        expected_loan_1_postings = [
            *self.expected_repayment_postings(
                loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                repayment_address=address.PRINCIPAL_DUE,
                amount=Decimal("100"),
            ),
            *self.expected_repayment_postings(
                loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                repayment_address=address.PRINCIPAL,
                repayment_from_address=address.OVERPAYMENT,
                amount=Decimal("50"),
            ),
            *self.expected_overpayment_tracker_postings(loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID),
            *self.expected_repayment_postings(
                loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                repayment_address=address.ACCRUED_INTEREST_RECEIVABLE,
                amount=Decimal("0.12"),
            ),
        ]

        expected_loan_2_postings = [
            *self.expected_repayment_postings(
                loan_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
                repayment_address=address.PRINCIPAL_DUE,
                amount=Decimal("100"),
            ),
            *self.expected_repayment_postings(
                loan_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
                repayment_address=address.PRINCIPAL,
                repayment_from_address=address.OVERPAYMENT,
                amount=Decimal("45.12"),
            ),
            *self.expected_overpayment_tracker_postings(loan_account_id=DEFAULT_LOAN_2_ACCOUNT_ID),
        ]

        expected_loc_postings = [
            *self.expected_overpayment_fee_postings(amount=Decimal("5.00")),
        ]

        mock_loan_1.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_1_postings,
            effective_date=DEFAULT_DATE,
            client_batch_id=f"REPAYMENT_{mock_loan_1.account_id}_MOCK_HOOK",
            batch_details={"force_override": "true"},
        )

        mock_loan_2.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_2_postings,
            effective_date=DEFAULT_DATE,
            client_batch_id=f"REPAYMENT_{mock_loan_2.account_id}_MOCK_HOOK",
            batch_details={"force_override": "true"},
        )

        mock_loc.instruct_posting_batch.assert_has_calls(
            [
                call(
                    posting_instructions=expected_loc_postings,
                    effective_date=DEFAULT_DATE,
                    client_batch_id=f"REPAYMENT_{mock_loc.account_id}_MOCK_HOOK",
                    batch_details={"force_override": "true"},
                ),
                call(
                    posting_instructions=ANY,
                    effective_date=DEFAULT_DATE,
                    client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
                    batch_details={"force_override": "True"},
                ),
            ]
        )

    def test_repaying_rounded_up_accrued_interest(self):
        loan_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal=Decimal("0"),
            # rounds to 0.13, so we expect an 0.005 extra accrual posting
            accrued_interest_receivable=Decimal("0.125"),
        )

        mock_vault, mock_loan_1, mock_loan_2, mock_loc = self.get_default_setup(
            loan_1_balance_ts=loan_balance_ts, loan_2_balance_ts=loan_balance_ts
        )
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("0.26"),
                    instruction_details={
                        "description": "Repayment from a customer",
                        "event": "INCOMING_REPAYMENT",
                    },
                )
            ]
        )

        self.run_function("post_posting_code", mock_vault, postings, DEFAULT_DATE)

        expected_loan_1_postings = [
            *self.expected_repayment_postings(
                loan_account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                repayment_address=address.ACCRUED_INTEREST_RECEIVABLE,
                amount=Decimal("0.13"),
            ),
            *self.expected_accrual_postings(
                account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
                amount=Decimal("0.005"),
                instruction_details={
                    "description": "Adjust accrued interest to handle repayment rounding",
                    "event": "ACCRUE_INTEREST",
                },
            ),
        ]

        expected_loan_2_postings = [
            *self.expected_repayment_postings(
                loan_account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
                repayment_address=address.ACCRUED_INTEREST_RECEIVABLE,
                amount=Decimal("0.13"),
            ),
            *self.expected_accrual_postings(
                account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
                amount=Decimal("0.005"),
                instruction_details={
                    "description": "Adjust accrued interest to handle repayment rounding",
                    "event": "ACCRUE_INTEREST",
                },
            ),
        ]

        mock_loan_1.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_1_postings,
            effective_date=DEFAULT_DATE,
            client_batch_id=f"REPAYMENT_{mock_loan_1.account_id}_MOCK_HOOK",
            batch_details={"force_override": "true"},
        )

        mock_loan_2.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_2_postings,
            effective_date=DEFAULT_DATE,
            client_batch_id=f"REPAYMENT_{mock_loan_2.account_id}_MOCK_HOOK",
            batch_details={"force_override": "true"},
        )

        mock_loc.instruct_posting_batch.assert_has_calls(
            [
                call(
                    posting_instructions=ANY,
                    effective_date=DEFAULT_DATE,
                    client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
                    batch_details={"force_override": "True"},
                ),
            ]
        )

    def test_override_posting_no_ops_in_post_posting(self):
        loan_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal_due=Decimal("100"),
            principal=Decimal("50"),
        )

        mock_vault, mock_loan_1, mock_loan_2, mock_loc = self.get_default_setup(
            loan_1_balance_ts=loan_balance_ts, loan_2_balance_ts=loan_balance_ts
        )
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("300"),
                    instruction_details={
                        "description": "Repayment from a customer",
                        "event": "INCOMING_REPAYMENT",
                    },
                )
            ],
            batch_details={"force_override": "true"},
        )
        self.run_function("post_posting_code", mock_vault, postings, DEFAULT_DATE)

        mock_loan_1.instruct_posting_batch.assert_not_called()
        mock_loan_2.instruct_posting_batch.assert_not_called()
        mock_loc.instruct_posting_batch.assert_not_called()

    def test_notification_sent_for_loan_final_repayment(self):
        loan_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE, principal_due=Decimal("100"), principal=Decimal("0")
        )
        mock_vault, _, _, mock_loc = self.get_default_setup(loan_1_balance_ts=loan_balance_ts)
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("100"),
                    instruction_details={
                        "description": "Repayment from a customer",
                        "event": "INCOMING_REPAYMENT",
                    },
                )
            ]
        )
        self.run_function("post_posting_code", mock_vault, postings, DEFAULT_DATE)

        mock_loc.instruct_notification.assert_called_once_with(
            notification_type="LINE_OF_CREDIT_LOANS_PAID_OFF",
            notification_details={"account_ids": f'["{DEFAULT_LOAN_1_ACCOUNT_ID}"]'},
        )

    def test_notification_sent_for_multiple_loan_final_repayment(self):
        loan_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE, principal_due=Decimal("100"), principal=Decimal("0")
        )
        mock_vault, _, _, mock_loc = self.get_default_setup(
            loan_1_balance_ts=loan_balance_ts,
            loan_2_balance_ts=loan_balance_ts,
        )
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("200"),
                    instruction_details={
                        "description": "Repayment from a customer",
                        "event": "INCOMING_REPAYMENT",
                    },
                )
            ]
        )
        self.run_function("post_posting_code", mock_vault, postings, DEFAULT_DATE)

        mock_loc.instruct_notification.assert_called_once_with(
            notification_type="LINE_OF_CREDIT_LOANS_PAID_OFF",
            notification_details={
                "account_ids": f'["{DEFAULT_LOAN_1_ACCOUNT_ID}", "{DEFAULT_LOAN_2_ACCOUNT_ID}"]'
            },
        )

    def test_notification_sent_for_loan_final_repayment_loc_itself_if_penalties_repaid(self):
        loan_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE, principal_due=Decimal("100"), principal=Decimal("0")
        )
        loc_balance_ts = self.balances_for_loc_account(penalties=Decimal("10"))
        mock_vault, _, _, mock_loc = self.get_default_setup(
            loan_1_balance_ts=loan_balance_ts, loc_balance_ts=loc_balance_ts
        )
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("110"),
                    instruction_details={
                        "description": "Repayment from a customer",
                        "event": "INCOMING_REPAYMENT",
                    },
                )
            ]
        )
        self.run_function("post_posting_code", mock_vault, postings, DEFAULT_DATE)

        mock_loc.instruct_notification.assert_called_once_with(
            notification_type="LINE_OF_CREDIT_LOANS_PAID_OFF",
            notification_details={"account_ids": f'["{DEFAULT_LOAN_1_ACCOUNT_ID}"]'},
        )

    def test_notification_sent_when_early_repaying_a_loan(self):
        loan_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE, principal_due=Decimal("100"), principal=Decimal("50")
        )
        mock_vault, _, _, mock_loc = self.get_default_setup(
            loan_1_balance_ts=loan_balance_ts,
        )
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    # includes late repayment fee
                    amount=Decimal("152.5"),
                    instruction_details={
                        "description": "Repayment from a customer",
                        "event": "INCOMING_REPAYMENT",
                    },
                )
            ]
        )
        self.run_function("post_posting_code", mock_vault, postings, DEFAULT_DATE)

        mock_loc.instruct_notification.assert_called_once_with(
            notification_type="LINE_OF_CREDIT_LOANS_PAID_OFF",
            notification_details={"account_ids": f'["{DEFAULT_LOAN_1_ACCOUNT_ID}"]'},
        )

    def test_notification_not_sent_when_partially_repaying_a_loan(self):
        loan_balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE, principal_due=Decimal("100"), principal=Decimal("0")
        )
        mock_vault, _, _, mock_loc = self.get_default_setup(
            loan_1_balance_ts=loan_balance_ts,
            loan_2_balance_ts=loan_balance_ts,
        )
        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(
                    amount=Decimal("50"),
                    instruction_details={
                        "description": "Repayment from a customer",
                        "event": "INCOMING_REPAYMENT",
                    },
                )
            ]
        )
        self.run_function("post_posting_code", mock_vault, postings, DEFAULT_DATE)

        mock_loc.instruct_notification.assert_not_called()


# These tests focus on the integration between template and features
class FeatureIntegrationTest(LOCTest):
    def test_interest_accrual(self):
        last_execution_time = datetime(2020, 5, 10, 0, 0, 2)
        effective_date = datetime(2020, 6, 10, 0, 0, 2)
        loan_balances = self.balances_for_loan_account(
            overpayment=Decimal("100"), emi_principal_excess=Decimal("0.21")
        )
        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            days_in_year=UnionItem("365"),
            loan_start_date=datetime(2020, 1, 1),
            balance_ts=loan_balances,
            make_instructions_return_full_objects=True,
        )
        mock_vault_loan_2 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            days_in_year=UnionItem("365"),
            loan_start_date=datetime(2020, 1, 1),
            balance_ts=loan_balances,
            make_instructions_return_full_objects=True,
        )
        mock_vault_loc = self.create_default_loc_supervisee_mock(
            account_id=DEFAULT_LOC_ACCOUNT_ID,
            DUE_AMOUNT_CALCULATION=last_execution_time,
            make_instructions_return_full_objects=True,
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOAN_2_ACCOUNT_ID: mock_vault_loan_2,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        # Balance for loan 1 also has 100 overpayment and 0.21 excess principal
        expected_loan_1_postings = self.expected_accrual_postings(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            # round(1000 * 0.031 / 365, 5)
            amount=Decimal("0.08493"),
            effective_balance=Decimal("1000"),
        ) + self.expected_overpayment_accrual_postings(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            # round(1100.21 * 0.031 / 365, 5)
            amount=Decimal("0.09344"),
            effective_balance=Decimal("1100.21"),
        )
        expected_loan_2_postings = self.expected_accrual_postings(
            account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            amount=Decimal("0.08493"),
            effective_balance=Decimal("1000"),
        ) + self.expected_overpayment_accrual_postings(
            account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            amount=Decimal("0.09344"),
            effective_balance=Decimal("1100.21"),
        )

        expected_loc_postings = self.expected_aggregate_postings(
            account_id=DEFAULT_LOC_ACCOUNT_ID,
            address=interest_accrual.ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
            aggregate_prefix="TOTAL",
            # sum of rounded accruals = 2 * round(0.08493,2) -> 0.16
            amount=Decimal("0.16"),
        )
        mock_vault = self.create_supervisor_mock(supervisees=supervisees)

        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type=interest_accrual.ACCRUAL_EVENT,
            effective_date=effective_date,
        )

        mock_vault_loan_1.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_1_postings,
            effective_date=effective_date,
            client_batch_id=f"{interest_accrual.ACCRUAL_EVENT}_{self.hook_execution_id}",
            batch_details={"event": interest_accrual.ACCRUAL_EVENT},
        )
        mock_vault_loan_2.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_2_postings,
            effective_date=effective_date,
            client_batch_id=f"{interest_accrual.ACCRUAL_EVENT}_{self.hook_execution_id}",
            batch_details={"event": interest_accrual.ACCRUAL_EVENT},
        )
        mock_vault_loc.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loc_postings,
            effective_date=effective_date,
            client_batch_id=f"AGGREGATE_LOC_{self.hook_execution_id}",
            batch_details={"force_override": "True"},
        )

    def test_due_amount_calculation_with_overpayment_reduce_term(
        self,
    ):
        last_execution_time = datetime(2020, 5, 10, 0, 0, 2)
        effective_date = datetime(2020, 6, 10, 0, 0, 2)
        balance_ts = self.balances_for_loan_account(
            # will round up on application
            accrued_interest_receivable=Decimal("10.109"),
            # will trigger emi principal excess
            accrued_expected_interest=Decimal("10.15"),
            overpayment=Decimal("100"),
        )
        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            balance_ts=balance_ts,
            loan_start_date=datetime(2020, 1, 1),
            make_instructions_return_full_objects=True,
        )
        mock_vault_loan_2 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            balance_ts=balance_ts,
            loan_start_date=datetime(2020, 1, 1),
            make_instructions_return_full_objects=True,
        )
        mock_vault_loc = self.create_default_loc_supervisee_mock(
            DUE_AMOUNT_CALCULATION=last_execution_time,
            flags=[""],
            due_amount_calculation_blocking_flags=dumps(["REPAYMENT_HOLIDAY"]),
            overpayment_impact_preference=UnionItem("reduce_term"),
            make_instructions_return_full_objects=True,
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOAN_2_ACCOUNT_ID: mock_vault_loan_2,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        expected_loan_postings = [
            [
                # stored EMI is not 0 and no reamortisation, so no EMI updates
                # Principal due updated as expected (emi=250)
                *self.expected_principal_due_postings(account_id=loan_id, amount=Decimal("239.89")),
                # interest is applied and residual amounts are cleared
                *self.expected_application_postings(
                    account_id=loan_id,
                    apply_amount=Decimal("10.11"),
                    accrue_amount=Decimal("10.109"),
                ),
                # this is always cleared if overpayment feature is used
                *self.expected_overpayment_application_postings(
                    account_id=loan_id, amount=Decimal("10.15")
                ),
                # test is set up to have higher expected interest than accrued interest
                *self.expected_emi_excess_postings(account_id=loan_id, amount=Decimal("0.04")),
            ]
            for loan_id in [DEFAULT_LOAN_1_ACCOUNT_ID, DEFAULT_LOAN_2_ACCOUNT_ID]
        ]

        expected_loc_postings = [
            # moved from PRINCIPAL TO PRINCIPAL_DUE
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.PRINCIPAL,
                aggregate_prefix="TOTAL",
                # sum of both principals
                amount=Decimal("479.78"),
                credit_aggregate_address=True,
            ),
            # total principal due
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.PRINCIPAL_DUE,
                aggregate_prefix="TOTAL",
                # sum of both principals
                amount=Decimal("479.78"),
            ),
            # total interest due
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.INTEREST_DUE,
                aggregate_prefix="TOTAL",
                # sum of interest due
                amount=Decimal("20.22"),
            ),
            # moved from ACC_INT_RECEIVABLE to INTEREST_DUE
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.ACCRUED_INTEREST_RECEIVABLE,
                aggregate_prefix="TOTAL",
                amount=Decimal("20.22"),
                credit_aggregate_address=True,
            ),
        ]

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type=debt_management.DUE_AMOUNT_CALCULATION,
            effective_date=effective_date,
        )

        mock_vault_loan_1.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_postings[0],
            effective_date=effective_date,
            client_batch_id=f"{debt_management.DUE_AMOUNT_CALCULATION}_{self.hook_execution_id}",
            batch_details={"event": debt_management.DUE_AMOUNT_CALCULATION},
        )
        mock_vault_loan_2.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_postings[1],
            effective_date=effective_date,
            client_batch_id=f"{debt_management.DUE_AMOUNT_CALCULATION}_{self.hook_execution_id}",
            batch_details={"event": debt_management.DUE_AMOUNT_CALCULATION},
        )
        mock_vault_loc.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loc_postings,
            effective_date=effective_date,
            client_batch_id=f"AGGREGATE_LOC_{self.hook_execution_id}",
            batch_details={"force_override": "True"},
        )
        mock_vault_loc.instruct_notification.assert_called_once_with(
            notification_type="LINE_OF_CREDIT_REPAYMENT",
            notification_details={
                "account_id": DEFAULT_LOC_ACCOUNT_ID,
                "repayment_amount": "500.00",
                "overdue_date": str((effective_date + relativedelta(days=5)).date()),
            },
        )

    def test_due_amount_calculation_no_pis(
        self,
    ):
        last_execution_time = datetime(2020, 5, 10, 0, 0, 2)
        effective_date = datetime(2020, 6, 10, 0, 0, 2)
        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            balance_ts=self.balances_for_loan_account(),
            creation_date=datetime(2020, 5, 15),
            # loan less than a month old
            loan_start_date=datetime(2020, 5, 15),
        )
        mock_vault_loc = self.create_default_loc_supervisee_mock(
            DUE_AMOUNT_CALCULATION=last_execution_time,
            due_amount_calculation_blocking_flags=dumps(["REPAYMENT_HOLIDAY"]),
            overpayment_impact_preference=UnionItem("reduce_term"),
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="DUE_AMOUNT_CALCULATION",
            effective_date=effective_date,
        )

        mock_vault_loan_1.instruct_posting_batch.assert_not_called()
        mock_vault_loc.instruct_notification.assert_not_called()

    def test_check_overdue_grace_period_0_mark_delinquent(self):
        balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal=Decimal("100000"),
            accrued_interest_receivable=Decimal("0"),
            principal_due=Decimal("1000"),
            interest_due=Decimal("350"),
        )

        effective_date = DEFAULT_DATE + relativedelta(months=1)
        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            balance_ts=balance_ts,
            make_instructions_return_full_objects=True,
        )
        mock_vault_loan_2 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            balance_ts=balance_ts,
            make_instructions_return_full_objects=True,
        )
        mock_vault_loc = self.create_default_loc_supervisee_mock(
            make_instructions_return_full_objects=True,
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOAN_2_ACCOUNT_ID: mock_vault_loan_2,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        expected_loan_postings = [
            [
                *self.expected_principal_overdue_postings(loan_id, Decimal("1000")),
                *self.expected_interest_overdue_postings(loan_id, Decimal("350")),
            ]
            for loan_id in [DEFAULT_LOAN_1_ACCOUNT_ID, DEFAULT_LOAN_2_ACCOUNT_ID]
        ]

        expected_loc_fee_postings = [*self.expected_late_repayment_fee_postings(Decimal("25"))]
        expected_loc_aggregate_postings = [
            # moved from PRINCIPAL_DUE to PRINCIPAL_OVERDUE
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.PRINCIPAL_DUE,
                aggregate_prefix="TOTAL",
                # sum of both principals
                amount=Decimal("2000"),
                credit_aggregate_address=True,
            ),
            # total principal due
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.PRINCIPAL_OVERDUE,
                aggregate_prefix="TOTAL",
                # sum of both principals
                amount=Decimal("2000"),
            ),
            # moved from INTEREST_DUE to INTEREST_OVERDUE
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.INTEREST_DUE,
                aggregate_prefix="TOTAL",
                # sum of interest due
                amount=Decimal("700"),
                credit_aggregate_address=True,
            ),
            # total interest due
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.INTEREST_OVERDUE,
                aggregate_prefix="TOTAL",
                # sum of interest due
                amount=Decimal("700"),
            ),
        ]

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="CHECK_OVERDUE",
            effective_date=effective_date,
        )

        mock_vault_loan_1.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_postings[0], effective_date=effective_date
        )
        mock_vault_loan_2.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_postings[1], effective_date=effective_date
        )
        mock_vault_loc.instruct_posting_batch.assert_has_calls(
            [
                call(
                    posting_instructions=expected_loc_aggregate_postings,
                    effective_date=effective_date,
                    client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
                    batch_details={"force_override": "True"},
                ),
                call(posting_instructions=expected_loc_fee_postings, effective_date=effective_date),
            ]
        )
        mock_vault_loc.instruct_notification.assert_called_once_with(
            notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
            notification_details={
                "account_id": DEFAULT_LOC_ACCOUNT_ID,
                "repayment_amount": "2700",
                "late_repayment_fee": "25",
                "overdue_date": str(effective_date.date()),
            },
        )
        mock_vault_loc.start_workflow.assert_called_once_with(
            workflow="LINE_OF_CREDIT_MARK_DELINQUENT",
            context={"account_id": DEFAULT_LOC_ACCOUNT_ID},
        )

    def test_check_overdue_grace_period_0_already_delinquent(self):
        balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal=Decimal("100000"),
            accrued_interest_receivable=Decimal("0"),
            principal_due=Decimal("1000"),
            interest_due=Decimal("350"),
        )

        effective_date = DEFAULT_DATE + relativedelta(months=1)
        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            balance_ts=balance_ts,
            make_instructions_return_full_objects=True,
        )
        mock_vault_loan_2 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            balance_ts=balance_ts,
            make_instructions_return_full_objects=True,
        )
        mock_vault_loc = self.create_default_loc_supervisee_mock(
            # already delinquent
            flags={"ACCOUNT_DELINQUENT": [(DEFAULT_DATE, True)]},
            make_instructions_return_full_objects=True,
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOAN_2_ACCOUNT_ID: mock_vault_loan_2,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        expected_loan_postings = [
            [
                *self.expected_principal_overdue_postings(loan_id, Decimal("1000")),
                *self.expected_interest_overdue_postings(loan_id, Decimal("350")),
            ]
            for loan_id in [DEFAULT_LOAN_1_ACCOUNT_ID, DEFAULT_LOAN_2_ACCOUNT_ID]
        ]

        expected_loc_fee_postings = [*self.expected_late_repayment_fee_postings(Decimal("25"))]
        expected_loc_aggregate_postings = [
            # moved from PRINCIPAL_DUE to PRINCIPAL_OVERDUE
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.PRINCIPAL_DUE,
                aggregate_prefix="TOTAL",
                # sum of both principals
                amount=Decimal("2000"),
                credit_aggregate_address=True,
            ),
            # total principal due
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.PRINCIPAL_OVERDUE,
                aggregate_prefix="TOTAL",
                # sum of both principals
                amount=Decimal("2000"),
            ),
            # moved from INTEREST_DUE to INTEREST_OVERDUE
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.INTEREST_DUE,
                aggregate_prefix="TOTAL",
                # sum of interest due
                amount=Decimal("700"),
                credit_aggregate_address=True,
            ),
            # total interest due
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.INTEREST_OVERDUE,
                aggregate_prefix="TOTAL",
                # sum of interest due
                amount=Decimal("700"),
            ),
        ]

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="CHECK_OVERDUE",
            effective_date=effective_date,
        )

        mock_vault_loan_1.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_postings[0], effective_date=effective_date
        )
        mock_vault_loan_2.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_postings[1], effective_date=effective_date
        )
        mock_vault_loc.instruct_posting_batch.assert_has_calls(
            [
                call(
                    posting_instructions=expected_loc_aggregate_postings,
                    effective_date=effective_date,
                    client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
                    batch_details={"force_override": "True"},
                ),
                call(posting_instructions=expected_loc_fee_postings, effective_date=effective_date),
            ]
        )

        # overdue repayment notification, no MARK_DELINQUENT call
        mock_vault_loc.instruct_notification.assert_called_once_with(
            notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
            notification_details={
                "account_id": DEFAULT_LOC_ACCOUNT_ID,
                "repayment_amount": "2700",
                "late_repayment_fee": "25",
                "overdue_date": str(effective_date.date()),
            },
        )

    def test_check_overdue_no_due_amounts(self):
        balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal=Decimal("100000"),
            accrued_interest_receivable=Decimal("0"),
            principal_due=Decimal("0"),
            interest_due=Decimal("0"),
        )

        effective_date = DEFAULT_DATE + relativedelta(months=1)
        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            balance_ts=balance_ts,
        )
        mock_vault_loc = self.create_default_loc_supervisee_mock(grace_period=Decimal("2"))

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="CHECK_OVERDUE",
            effective_date=effective_date,
        )

        mock_vault_loan_1.instruct_posting_batch.assert_not_called()
        mock_vault_loc.instruct_posting_batch.assert_not_called()
        mock_vault_loc.instruct_notification.assert_not_called()
        mock_vault_loc.start_workflow.assert_not_called()
        mock_vault.update_event_type.assert_called_with(
            event_type="CHECK_DELINQUENCY",
            schedule=EventTypeSchedule(
                year="2019",
                month="3",
                day="6",
                hour="0",
                minute="2",
                second="0",
            ),
        )

    def test_check_overdue_no_late_fee(self):
        balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal=Decimal("100000"),
            accrued_interest_receivable=Decimal("0"),
            principal_due=Decimal("1000"),
            interest_due=Decimal("350"),
        )

        effective_date = DEFAULT_DATE + relativedelta(months=1)
        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            balance_ts=balance_ts,
            make_instructions_return_full_objects=True,
        )
        mock_vault_loc = self.create_default_loc_supervisee_mock(
            late_repayment_fee=Decimal("0"),
            make_instructions_return_full_objects=True,
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        expected_loan_postings = [
            *self.expected_principal_overdue_postings(DEFAULT_LOAN_1_ACCOUNT_ID, Decimal("1000")),
            *self.expected_interest_overdue_postings(DEFAULT_LOAN_1_ACCOUNT_ID, Decimal("350")),
        ]

        expected_loc_aggregate_postings = [
            # moved from PRINCIPAL_DUE to PRINCIPAL_OVERDUE
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.PRINCIPAL_DUE,
                aggregate_prefix="TOTAL",
                # sum of both principals
                amount=Decimal("1000"),
                credit_aggregate_address=True,
            ),
            # total principal due
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.PRINCIPAL_OVERDUE,
                aggregate_prefix="TOTAL",
                # sum of both principals
                amount=Decimal("1000"),
            ),
            # moved from INTEREST_DUE to INTEREST_OVERDUE
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.INTEREST_DUE,
                aggregate_prefix="TOTAL",
                # sum of interest due
                amount=Decimal("350"),
                credit_aggregate_address=True,
            ),
            # total interest due
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.INTEREST_OVERDUE,
                aggregate_prefix="TOTAL",
                # sum of interest due
                amount=Decimal("350"),
            ),
        ]

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="CHECK_OVERDUE",
            effective_date=effective_date,
        )

        mock_vault_loan_1.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_postings, effective_date=effective_date
        )
        mock_vault_loc.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loc_aggregate_postings,
            effective_date=effective_date,
            client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
            batch_details={"force_override": "True"},
        )
        mock_vault_loc.instruct_notification.assert_called_once_with(
            notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
            notification_details={
                "account_id": DEFAULT_LOC_ACCOUNT_ID,
                "repayment_amount": "1350",
                "late_repayment_fee": "0",
                "overdue_date": str(effective_date.date()),
            },
        )
        mock_vault_loc.start_workflow.assert_called_once_with(
            workflow="LINE_OF_CREDIT_MARK_DELINQUENT",
            context={"account_id": DEFAULT_LOC_ACCOUNT_ID},
        )

    def test_check_overdue_5_day_grace_period(self):
        balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal=Decimal("100000"),
            accrued_interest_receivable=Decimal("0"),
            principal_due=Decimal("1000"),
            interest_due=Decimal("350"),
        )

        effective_date = DEFAULT_DATE + relativedelta(months=1)
        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            balance_ts=balance_ts,
            make_instructions_return_full_objects=True,
        )
        mock_vault_loan_2 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_2_ACCOUNT_ID,
            balance_ts=balance_ts,
            make_instructions_return_full_objects=True,
        )
        mock_vault_loc = self.create_default_loc_supervisee_mock(
            grace_period=Decimal("5"),
            make_instructions_return_full_objects=True,
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOAN_2_ACCOUNT_ID: mock_vault_loan_2,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        expected_loan_postings = [
            [
                *self.expected_principal_overdue_postings(loan_id, Decimal("1000")),
                *self.expected_interest_overdue_postings(loan_id, Decimal("350")),
            ]
            for loan_id in [DEFAULT_LOAN_1_ACCOUNT_ID, DEFAULT_LOAN_2_ACCOUNT_ID]
        ]

        expected_loc_fee_postings = [*self.expected_late_repayment_fee_postings(Decimal("25"))]
        expected_loc_aggregate_postings = [
            # moved from PRINCIPAL_DUE to PRINCIPAL_OVERDUE
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.PRINCIPAL_DUE,
                aggregate_prefix="TOTAL",
                # sum of both principals
                amount=Decimal("2000"),
                credit_aggregate_address=True,
            ),
            # total principal due
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.PRINCIPAL_OVERDUE,
                aggregate_prefix="TOTAL",
                # sum of both principals
                amount=Decimal("2000"),
            ),
            # moved from INTEREST_DUE to INTEREST_OVERDUE
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.INTEREST_DUE,
                aggregate_prefix="TOTAL",
                # sum of interest due
                amount=Decimal("700"),
                credit_aggregate_address=True,
            ),
            # total interest due
            *self.expected_aggregate_postings(
                account_id=DEFAULT_LOC_ACCOUNT_ID,
                address=address.INTEREST_OVERDUE,
                aggregate_prefix="TOTAL",
                # sum of interest due
                amount=Decimal("700"),
            ),
        ]
        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="CHECK_OVERDUE",
            effective_date=effective_date,
        )

        mock_vault_loan_1.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_postings[0], effective_date=effective_date
        )
        mock_vault_loan_2.instruct_posting_batch.assert_called_once_with(
            posting_instructions=expected_loan_postings[1], effective_date=effective_date
        )
        mock_vault_loc.instruct_posting_batch.assert_has_calls(
            [
                call(
                    posting_instructions=expected_loc_aggregate_postings,
                    effective_date=effective_date,
                    client_batch_id="AGGREGATE_LOC_MOCK_HOOK",
                    batch_details={"force_override": "True"},
                ),
                call(posting_instructions=expected_loc_fee_postings, effective_date=effective_date),
            ]
        )
        mock_vault_loc.instruct_notification.assert_called_once_with(
            notification_type="LINE_OF_CREDIT_OVERDUE_REPAYMENT",
            notification_details={
                "account_id": DEFAULT_LOC_ACCOUNT_ID,
                "repayment_amount": "2700",
                "late_repayment_fee": "25",
                "overdue_date": str(effective_date.date()),
            },
        )
        mock_vault.update_event_type.assert_called_with(
            event_type="CHECK_DELINQUENCY",
            schedule=EventTypeSchedule(
                year="2019",
                month="2",
                day="6",
                hour="0",
                minute="2",
                second="0",
            ),
        )

    def test_check_delinquency_no_late_balance(self):
        balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal=Decimal("100000"),
            accrued_interest_receivable=Decimal("0"),
        )

        effective_date = DEFAULT_DATE + relativedelta(months=1)
        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            balance_ts=balance_ts,
        )
        mock_vault_loc = self.create_default_loc_supervisee_mock(
            late_repayment_fee=Decimal("0"),
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="CHECK_DELINQUENCY",
            effective_date=effective_date,
        )

        mock_vault_loc.start_workflow.assert_not_called()

    def test_check_delinquency_late_balance(self):
        balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal=Decimal("100000"),
            accrued_interest_receivable=Decimal("0"),
            principal_overdue=Decimal("1000"),
            interest_overdue=Decimal("350"),
        )

        effective_date = DEFAULT_DATE + relativedelta(months=1)
        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            balance_ts=balance_ts,
        )
        mock_vault_loc = self.create_default_loc_supervisee_mock(
            late_repayment_fee=Decimal("0"),
            delinquency_flags=dumps(["ACCOUNT_DELINQUENT"]),
            flags={"ACCOUNT_DELINQUENT": [(DEFAULT_DATE, False)]},
            grace_period=Decimal("0"),
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="CHECK_DELINQUENCY",
            effective_date=effective_date,
        )

        mock_vault_loc.start_workflow.assert_called_once_with(
            workflow="LINE_OF_CREDIT_MARK_DELINQUENT",
            context={"account_id": DEFAULT_LOC_ACCOUNT_ID},
        )

    def test_check_delinquency_late_balance_already_delinquent(self):
        balance_ts = self.balances_for_loan_account(
            dt=DEFAULT_DATE,
            principal=Decimal("100000"),
            accrued_interest_receivable=Decimal("0"),
            principal_overdue=Decimal("1000"),
            interest_overdue=Decimal("350"),
        )

        effective_date = DEFAULT_DATE + relativedelta(months=1)
        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            balance_ts=balance_ts,
        )
        mock_vault_loc = self.create_default_loc_supervisee_mock(
            late_repayment_fee=Decimal("0"),
            delinquency_flags=dumps(["ACCOUNT_DELINQUENT"]),
            # already delinquent
            flags={"ACCOUNT_DELINQUENT": [(DEFAULT_DATE, True)]},
            grace_period=Decimal("0"),
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="CHECK_DELINQUENCY",
            effective_date=effective_date,
        )

        mock_vault_loc.start_workflow.assert_not_called()

    def test_overdue_check_is_blocked_if_flag_applied(self):
        last_execution_time = datetime(2020, 5, 10, 0, 0, 2)

        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            loan_start_date=datetime(2020, 1, 1),
            balance_ts=self.balances_for_loan_account(),
        )

        mock_vault_loc = self.create_default_loc_supervisee_mock(
            flags=["REPAYMENT_HOLIDAY"],
            DUE_AMOUNT_CALCULATION=last_execution_time,
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="CHECK_OVERDUE",
            effective_date=datetime(2020, 6, 10, 0, 0, 2),
        )

        mock_vault_loan_1.instruct_posting_batch.assert_not_called()
        mock_vault_loc.instruct_posting_batch.assert_not_called()

    def test_delinquency_check_is_blocked_if_flag_applied(self):
        last_execution_time = datetime(2020, 5, 10, 0, 0, 2)

        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            loan_start_date=datetime(2020, 1, 1),
            balance_ts=self.balances_for_loan_account(),
        )

        mock_vault_loc = self.create_default_loc_supervisee_mock(
            flags=["REPAYMENT_HOLIDAY"],
            DUE_AMOUNT_CALCULATION=last_execution_time,
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="CHECK_DELINQUENCY",
            effective_date=datetime(2020, 6, 10, 0, 0, 2),
        )

        mock_vault_loan_1.instruct_posting_batch.assert_not_called()
        mock_vault_loc.start_workflow.assert_not_called()


# These tests focus on the template code itself, excluding features
class AccrualBlockingTests(LOCTest):

    # Not adding additional tests as the utils feature is sufficiently covered
    def test_accrual_is_blocked_if_flag_applied(self):
        last_execution_time = datetime(2020, 5, 10, 0, 0, 2)

        mock_vault_loan_1 = self.create_default_drawdown_supervisee_mock(
            account_id=DEFAULT_LOAN_1_ACCOUNT_ID,
            loan_start_date=datetime(2020, 1, 1),
            balance_ts=self.balances_for_loan_account(),
        )

        mock_vault_loc = self.create_default_loc_supervisee_mock(
            flags=["REPAYMENT_HOLIDAY"],
            DUE_AMOUNT_CALCULATION=last_execution_time,
        )

        supervisees = {
            DEFAULT_LOAN_1_ACCOUNT_ID: mock_vault_loan_1,
            DEFAULT_LOC_ACCOUNT_ID: mock_vault_loc,
        }

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        self.run_function(
            "scheduled_code",
            mock_vault,
            event_type="ACCRUE_INTEREST",
            effective_date=datetime(2020, 6, 10, 0, 0, 2),
        )

        mock_vault_loan_1.instruct_posting_batch.assert_not_called()
        mock_vault_loc.instruct_posting_batch.assert_not_called()
