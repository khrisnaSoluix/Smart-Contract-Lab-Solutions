# Copyright @ 2024 Soluix Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo
from decimal import Decimal
from dateutil.relativedelta import relativedelta

# contracts api
from inception_sdk.test_framework.contracts.unit.contracts_api_extension import (
    Tside,
    AuthorisationAdjustment,
    CustomInstruction,
    InboundAuthorisation,
    InboundHardSettlement,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Release,
    Settlement,
    Transfer,

    BalancesObservation,
    BalanceDefaultDict,
    BalanceCoordinate,
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Phase,
    Balance,

    PrePostingHookArguments,
    ClientTransaction,
    PrePostingHookResult,
    Rejection,
    RejectionReason,

    ActivationHookArguments,
    PostingInstructionsDirective,
    Posting,
    FlagTimeseries,
    ScheduledEventHookArguments,
    UpdateAccountEventTypeDirective,
    ScheduledEventHookResult,
    ScheduleExpression,
    PreParameterChangeHookArguments,
    PreParameterChangeHookResult,
    DerivedParameterHookArguments,
    DerivedParameterHookResult
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.common import (
    ContractTest,
    construct_parameter_timeseries,
)

# import contract file
from exercise.bcas.saving_accounts.contracts.template import saving_accounts_exercise_3 as contract

DEFAULT_DATETIME = datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC"))
DEFAULT_ACCOUNT_ID = "Main account"
DEFAULT_INTERNAL_ACCOUNT = "1"
DEFAULT_DEPOSIT_BONUS_PAYOUT_INTERNAL_ACCOUNT = DEFAULT_INTERNAL_ACCOUNT
DEFAULT_ZAKAT_INTERNAL_ACCOUNT = DEFAULT_INTERNAL_ACCOUNT
DEFAULT_OPENING_BONUS = Decimal("100")
DEFAULT_ZAKAT_RATE = Decimal("0.02")

# parameters
DEFAULT_DENOMINATION = "IDR"

default_template_params = {
    "denomination": DEFAULT_DENOMINATION,
    "deposit_bonus_payout_internal_account": DEFAULT_DEPOSIT_BONUS_PAYOUT_INTERNAL_ACCOUNT,
    "zakat_internal_account": DEFAULT_ZAKAT_INTERNAL_ACCOUNT,
    "zakat_rate":DEFAULT_ZAKAT_RATE,
}
default_instance_params = {
    "opening_bonus": DEFAULT_OPENING_BONUS,
}

default_balances_observation_fetcher_mappings = {
    fetcher.fetcher_id: BalancesObservation(
        balances=BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination=DEFAULT_DENOMINATION,
                    phase=Phase.COMMITTED,
                ): Balance(credit=Decimal(0), debit=Decimal(0), net=(0))
            }
        ),
        value_datetime=DEFAULT_DATETIME,
    )
    for fetcher in contract.data_fetchers
}

_AllPITypes = (
    AuthorisationAdjustment,
    CustomInstruction,
    InboundAuthorisation,
    InboundHardSettlement,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Release,
    Settlement,
    Transfer,
)

class SavingAccount(ContractTest):
    tside = Tside.LIABILITY
    
    # Create mock 
    def create_mock(
        self,
        flags: Optional[dict[str, FlagTimeseries]] = None,
        account_id=DEFAULT_ACCOUNT_ID,
        creation_date=DEFAULT_DATETIME,
        template_params=default_template_params,
        instance_params=default_instance_params,
        balances_observation_fetchers_mapping=default_balances_observation_fetcher_mappings,
        **kwargs,
    ):

        params = template_params.copy() | instance_params.copy()
        parameter_ts = construct_parameter_timeseries(params, creation_date)
        return super().create_mock(
            account_id=account_id,
            parameter_ts=parameter_ts,
            creation_date=creation_date,
            flags_ts=flags,
            balances_observation_fetchers_mapping=balances_observation_fetchers_mapping,
            **kwargs,
        )
    # Exercise 1
    def test_pre_posting_hook_rejects_wrong_denomination(self):

        posting_amount = Decimal(10)

        inbound_hard_settlement = self.inbound_hard_settlement(
            amount=posting_amount,
            denomination="GBP",
            target_account_id=DEFAULT_ACCOUNT_ID,
            internal_account_id=DEFAULT_INTERNAL_ACCOUNT,
            own_account_id=DEFAULT_ACCOUNT_ID,
        )
        posting_instructions = [inbound_hard_settlement]

        hook_args = PrePostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            posting_instructions=posting_instructions,
            client_transactions=ClientTransaction(
                client_transaction_id="MOCK_POSTING",
                account_id=DEFAULT_ACCOUNT_ID,
                posting_instructions=posting_instructions,
                tside=contract.tside,
            ),
        )
        mock_vault = self.create_mock()
        pre_posting_response = contract.pre_posting_hook(mock_vault, hook_args)

        expected_response = PrePostingHookResult(
            rejection=Rejection(
                message=f"Postings are not allowed. Only postings in {DEFAULT_DENOMINATION} are accepted.",
                reason_code=RejectionReason.WRONG_DENOMINATION,
            )
        )
        self.assertEqual(
            pre_posting_response,
            expected_response,
        )
        
    # Exercise 2    
    def test_posting_for_opening_bonus(self):

        mock_vault = self.create_mock()
        hook_args = ActivationHookArguments(DEFAULT_DATETIME)
        activation_response = contract.activation_hook(mock_vault, hook_args)
        zakat=Decimal('2.00')
        expected_posting_instruction_directives = [
            PostingInstructionsDirective(
                posting_instructions=[
                    CustomInstruction(
                        postings=[
                            Posting(
                                credit=True,
                                amount=Decimal(DEFAULT_OPENING_BONUS),
                                denomination=DEFAULT_DENOMINATION,
                                account_id=DEFAULT_ACCOUNT_ID,
                                account_address=DEFAULT_ADDRESS,
                                asset=DEFAULT_ASSET,
                                phase=Phase.COMMITTED,
                            ),
                            Posting(
                                credit=False,
                                amount=Decimal(DEFAULT_OPENING_BONUS),
                                denomination=DEFAULT_DENOMINATION,
                                account_id=DEFAULT_INTERNAL_ACCOUNT,
                                account_address=DEFAULT_ADDRESS,
                                asset=DEFAULT_ASSET,
                                phase=Phase.COMMITTED,
                            ),
                        ],
                        instruction_details={
                            "description": "Opening bonus of 100 IDR paid.",
                            "event_type": "ACCOUNT_OPENING_BONUS",
                            "ext_client_transaction_id": "OPENING_BONUS_MOCK_HOOK",
                        },
                        override_all_restrictions=True,
                    ),
                    CustomInstruction(
                        postings=[
                            Posting(
                                credit=True,
                                amount=zakat,
                                denomination=DEFAULT_DENOMINATION,
                                account_id=DEFAULT_INTERNAL_ACCOUNT,
                                account_address=DEFAULT_ADDRESS,
                                asset=DEFAULT_ASSET,
                                phase=Phase.COMMITTED,
                            ),
                            Posting(
                                credit=False,
                                amount=zakat,
                                denomination=DEFAULT_DENOMINATION,
                                account_id=DEFAULT_ACCOUNT_ID,
                                account_address=DEFAULT_ADDRESS,
                                asset=DEFAULT_ASSET,
                                phase=Phase.COMMITTED,
                            ),
                        ],
                        instruction_details={
                            "description": "Zakat of 2.00 IDR paid.",
                            "event_type": "ACCOUNT_OPENING_BONUS",
                            "ext_client_transaction_id": "ZAKAT_MOCK_HOOK",
                        },
                        override_all_restrictions=True,
                    )
                ],
                value_datetime=DEFAULT_DATETIME,
            )
        ]

        self.assertEqual(
            expected_posting_instruction_directives,
            activation_response.posting_instructions_directives,
        )
    
    # Exercise 3
    def test_reject_zakat_rate_update(self):

        mock_vault = self.create_mock()

        parameters = {'zakat_rate': Decimal('0.03')}

        hook_args = PreParameterChangeHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            updated_parameter_values=parameters
        )

        pre_parameter_change_hook_response = contract.pre_parameter_change_hook(
            mock_vault,
            hook_arguments= hook_args
        )

        expected_response = PreParameterChangeHookResult(
            rejection=Rejection(
                message="Cannot update the zakat rate after account creation",
                reason_code=RejectionReason.AGAINST_TNC,
            )
        )

        self.assertEqual(pre_parameter_change_hook_response, expected_response)
    