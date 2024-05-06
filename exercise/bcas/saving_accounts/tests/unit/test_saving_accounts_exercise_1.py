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
from exercise.bcas.saving_accounts.contracts.template import saving_accounts_exercise_1 as contract

DEFAULT_DATETIME = datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC"))
DEFAULT_ACCOUNT_ID = "Main account"
DEFAULT_INTERNAL_ACCOUNT = "1"

# parameters
DEFAULT_DENOMINATION = "IDR"

default_template_params = {
    "denomination": DEFAULT_DENOMINATION,
}
default_instance_params = {}

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
