# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock
from zoneinfo import ZoneInfo

# contracts api
# It is very important to use contracts_api here and not any of the extension types. This is
# because the types here will be passed into the contract and must therefore be exactly as per the
# API (see documentation/testing/unit.md for more details)
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    AdjustmentAmount,
    AuthorisationAdjustment,
    Balance,
    BalanceCoordinate,
    BalancesObservation,
    BalanceTimeseries,
    CalendarEvent,
    CalendarEvents,
    ClientTransaction,
    CustomInstruction,
    FlagTimeseries,
    InboundAuthorisation,
    InboundHardSettlement,
    OptionalValue,
    OutboundAuthorisation,
    OutboundHardSettlement,
    ParameterTimeseries,
    Phase,
    Posting,
    PostPostingHookResult,
    PrePostingHookResult,
    Release,
    ScheduledEventHookResult,
    Settlement,
    TransactionCode,
    Transfer,
    Tside,
    UnionItemValue,
)

PostingInstruction = (
    AuthorisationAdjustment
    | CustomInstruction
    | InboundAuthorisation
    | InboundHardSettlement
    | OutboundAuthorisation
    | OutboundHardSettlement
    | Release
    | Settlement
    | Transfer
)


PostingInstructionTypeList = list[PostingInstruction]

ParameterValueType = Decimal | str | datetime | OptionalValue | UnionItemValue | int

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


DEFAULT_DATETIME = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
DEFAULT_DENOMINATION = "GBP"
DEFAULT_HOOK_EXECUTION_ID = "MOCK_HOOK"
DEFAULT_PHASE = Phase.COMMITTED
POSTING_CLIENT_ID = "client_id"
CLIENT_TRANSACTION_ID = "MOCK_POSTING"
ACCOUNT_ID = "default_account"
DEFAULT_INTERNAL_ACCOUNT = "1"


def construct_parameter_timeseries(
    parameter_name_to_value_map: dict[str, ParameterValueType], default_datetime: datetime
) -> dict[str, ParameterTimeseries]:
    """
    returns a dict where key is param name and value is a ParameterTimeseries object to
    be used as the parameter_ts for the mock vault object
    """
    return {
        param_name: ParameterTimeseries([(default_datetime, param_value)])
        for param_name, param_value in parameter_name_to_value_map.items()
    }


def construct_flag_timeseries(
    flag_name_to_bool_map: dict[str, bool], default_datetime: datetime
) -> dict[str, FlagTimeseries]:
    return {
        flag_name: FlagTimeseries([(default_datetime, flag_bool)])
        for flag_name, flag_bool in flag_name_to_bool_map.items()
    }


class ContractTest(TestCase):
    tside: Tside
    default_denomination: str = DEFAULT_DENOMINATION
    events_timezone: ZoneInfo = ZoneInfo("UTC")

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.tside
        except AttributeError:
            raise AttributeError(
                "You must supply the Tside of the product at the start of the test class"
            )

    def create_mock(
        self,
        account_id: str = ACCOUNT_ID,
        balances_observation_fetchers_mapping: dict[str, BalancesObservation] | None = None,
        balances_interval_fetchers_mapping: (
            dict[str, defaultdict[BalanceCoordinate, BalanceTimeseries]] | None
        ) = None,
        calendar_events: list[CalendarEvent] | None = None,
        client_transactions_mapping: dict[str, dict[str, ClientTransaction]] | None = None,
        creation_date: datetime = DEFAULT_DATETIME,
        existing_mock: Mock | None = None,
        flags_ts: dict[str, FlagTimeseries] | None = None,
        last_execution_datetimes: dict[str, datetime] | None | None = None,
        parameter_ts: dict[str, ParameterTimeseries] | None = None,
        postings_interval_mapping: dict[str, PostingInstructionTypeList] | None = None,
        requires_fetched_balances: defaultdict[BalanceCoordinate, BalanceTimeseries] | None = None,
        requires_fetched_client_transactions: dict[str, ClientTransaction] | None = None,
        requires_fetched_postings: PostingInstructionTypeList | None = None,
        supervisee_alias: str | None = None,
        supervisee_hook_result: (
            PostPostingHookResult | PrePostingHookResult | ScheduledEventHookResult | None
        ) = None,
        is_supervisee_vault: bool = False,
    ) -> Mock:
        """
        Create mock Vault object for the test

        All parameters are optional apart from account_id and creation_date.

        :param account_id: Account ID
        :param balances_observation_fetchers_mapping: mapping of fetcher_id to balance observation
        :param balances_interval_fetchers_mapping: mapping of fetcher_id to balance timeseries
        :param calendar_events: list of calendar events
        :param client_transactions_mapping: mapping of postings fetcher id to Client transactions
        including proposed
        :param creation_date: Account creation date
        :param existing_mock: some mock
        :param flags_ts: dict where key is flag name and value is a FlagTimeseries object
        :param last_execution_datetimes: dict of event_type to last execution datetime
        :param parameter_ts: dict where key is param name and value is a ParameterTimeseries object
        :param postings_interval_mapping: mapping of postings fetcher_id to posting instructions

        # supervisee specific arguments - these following arguments should only used on supervisee
        vault objects
        :param requires_fetched_balances: balances fetched from the requires decorator, this should
        only be used in the post_posting_hook or scheduled_event_hook where optimised data fetchers
        for supervisors are not yet supported
        :param requires_fetched_client_transactions: client transactions fetched from the requires
        decorator, this should only be used in the post_posting_hook or scheduled_event_hook where
        optimised data fetchers for supervisors are not yet supported
        :param requires_fetched_postings: postings fetched from the requires decorator, this should
        only be used in the post_posting_hook or scheduled_event_hook where optimised data fetchers
        for supervisors are not yet supported
        :param supervisee_alias: alias of the supervisee vault object
        :param supervisee_hook_result: returned hook result of the supervised hook
        :param is_supervisee_vault: boolean used to determine whether this is a supervisee vault
        object or not
        """

        parameter_ts = parameter_ts or {}
        flags_ts = flags_ts or {}
        calendar_events = calendar_events or []
        # replace CLU dependency syntax from flag definitions. This allows for consistency between
        # the contract and the tests since unit tests run the contract directly as a python module,
        # these aren't removed in any class setup or rendering
        flags_ts = {
            flag.replace("&{", "").replace("}", ""): datetime_bool
            for flag, datetime_bool in flags_ts.items()
        }

        calendar_events = [
            CalendarEvent(
                id=calendar_event.id,
                calendar_id=calendar_event.calendar_id.replace("&{", "").replace("}", ""),
                start_datetime=calendar_event.start_datetime,
                end_datetime=calendar_event.end_datetime,
            )
            for calendar_event in calendar_events
        ]

        last_execution_datetimes = last_execution_datetimes or {}
        client_transactions_mapping = client_transactions_mapping or {}
        balances_observation_fetchers_mapping = balances_observation_fetchers_mapping or {}
        balances_interval_fetchers_mapping = balances_interval_fetchers_mapping or {}
        postings_interval_mapping = postings_interval_mapping or {}

        def mock_get_balance_timeseries(
            fetcher_id: str | None = None,
        ) -> defaultdict[BalanceCoordinate, BalanceTimeseries]:
            if is_supervisee_vault:
                if requires_fetched_balances is not None:
                    return requires_fetched_balances

            if fetcher_id:
                balance_interval_ts = balances_interval_fetchers_mapping.get(fetcher_id)
                if not balance_interval_ts:
                    raise ValueError(f"Missing balance interval in test setup for {fetcher_id=}")
                else:
                    return balance_interval_ts
            else:
                raise ValueError("You must provide a fetcher ID")

        def mock_get_balances_observation(fetcher_id: str) -> BalancesObservation:
            balance_observation = balances_observation_fetchers_mapping.get(fetcher_id)
            if not balance_observation:
                raise ValueError(f"Missing balance observation in test setup for {fetcher_id=}")

            return balance_observation

        def mock_get_parameter_timeseries(
            name: str,
        ) -> ParameterTimeseries:
            if name in parameter_ts:
                parameter_timeseries = parameter_ts[name]
            else:
                raise KeyError(f"Parameter {name} not found in parameter timeseries.")
            return parameter_timeseries

        def mock_get_posting_instructions(
            fetcher_id: str | None = None,
        ) -> PostingInstructionTypeList:
            if is_supervisee_vault:
                if requires_fetched_postings is not None:
                    return requires_fetched_postings

            if fetcher_id:
                posting_instructions = postings_interval_mapping.get(fetcher_id)
                if posting_instructions is None:
                    raise ValueError(f"Missing posting interval in test setup for {fetcher_id=}")
                else:
                    return posting_instructions
            else:
                raise ValueError("You must provide a fetcher ID")

        def mock_get_calendar_events(calendar_ids: list[str]) -> CalendarEvents:
            # replace CLU dependency syntax from flag definitions. This allows for consistency
            # between the contract and the tests since unit tests run the contract directly as
            # a python module, these aren't removed in any class setup or rendering
            calendar_ids = [
                calendar_id.replace("&{", "").replace("}", "") for calendar_id in calendar_ids
            ]
            events = [event for event in calendar_events if event.calendar_id in calendar_ids]
            return CalendarEvents(calendar_events=events)

        def mock_get_flag_timeseries(flag: str) -> FlagTimeseries:
            # replace CLU dependency syntax from flag definitions. This allows for consistency
            # between the contract and the tests since unit tests run the contract directly as
            # a python module, these aren't removed in any class setup or rendering
            flag = flag.replace("&{", "").replace("}", "")

            if flag in flags_ts:
                # flag settings have been supplied as a timeseries
                flag_timeseries = flags_ts[flag]
            else:
                # No setting supplied for flag, so it is False as per Vault behaviour
                flag_timeseries = FlagTimeseries([(creation_date, False)])
            return flag_timeseries

        def mock_get_last_execution_datetime(event_type: str) -> datetime | None:
            try:
                return last_execution_datetimes[event_type]
            except KeyError:
                raise ValueError("Missing event_type in last_execution_datetimes mapping.")

        def mock_get_client_transaction(fetcher_id: str | None = None):
            if is_supervisee_vault:
                if fetcher_id:
                    raise ValueError(
                        "Supervisee vault object cannot provide fetcher_id to "
                        "get_client_transactions()"
                    )
                if requires_fetched_client_transactions is None:
                    raise ValueError("Missing requires fetched client transactions in test setup")
                else:
                    return requires_fetched_client_transactions

            if fetcher_id:
                client_transactions = client_transactions_mapping.get(fetcher_id)
                if client_transactions is None:
                    raise ValueError(f"Missing client transactions in test setup for {fetcher_id=}")
                else:
                    return client_transactions
            else:
                raise ValueError("You must provide a fetcher ID")

        # supervisee specific methods
        def mock_get_alias() -> str:
            if is_supervisee_vault:
                if supervisee_alias is not None:
                    return supervisee_alias
                else:
                    raise ValueError("No supervisee alias provided")

            else:
                raise ValueError(
                    "get_alias method cannot be called on a non-supervisee Vault object, "
                    "make sure the create_mock argument is set correctly"
                )

        def mock_get_hook_result() -> (
            PrePostingHookResult | PostPostingHookResult | ScheduledEventHookResult
        ):
            if is_supervisee_vault:
                if supervisee_hook_result:
                    return supervisee_hook_result
                else:
                    raise ValueError(
                        "get_hook_result must return one of PrePostingHookResult, "
                        "PostPostingHookResult, ScheduledEventHookResult"
                    )
            else:
                raise ValueError(
                    "get_hook_result method cannot be called on a non-supervisee Vault object, "
                    "make sure the create_mock argument is set correctly"
                )

        # Identify mocks more easily, especially in supervisor scenarios
        mock_vault = existing_mock or Mock(name=account_id)

        # attributes
        mock_vault.account_id = account_id
        mock_vault.tside = self.tside
        mock_vault.events_timezone = self.events_timezone

        # methods
        mock_vault.get_account_creation_datetime.return_value = creation_date
        mock_vault.get_balances_timeseries.side_effect = mock_get_balance_timeseries
        mock_vault.get_balances_observation.side_effect = mock_get_balances_observation
        mock_vault.get_calendar_events.side_effect = mock_get_calendar_events
        mock_vault.get_client_transactions.side_effect = mock_get_client_transaction
        mock_vault.get_hook_execution_id.return_value = DEFAULT_HOOK_EXECUTION_ID
        mock_vault.get_flag_timeseries.side_effect = mock_get_flag_timeseries
        mock_vault.get_last_execution_datetime = mock_get_last_execution_datetime
        mock_vault.get_parameter_timeseries.side_effect = mock_get_parameter_timeseries
        mock_vault.get_posting_instructions.side_effect = mock_get_posting_instructions
        mock_vault.get_permitted_denominations.return_value = [self.default_denomination]

        # supervisee specific methods
        mock_vault.get_alias.side_effect = mock_get_alias
        mock_vault.get_hook_result.side_effect = mock_get_hook_result

        return mock_vault

    # Posting Instruction types
    def inbound_auth(
        self,
        amount: Decimal,
        client_transaction_id: str = CLIENT_TRANSACTION_ID,
        denomination: str = "",
        target_account_id: str = ACCOUNT_ID,
        internal_account_id: str = DEFAULT_INTERNAL_ACCOUNT,
        advice: bool | None = False,
        instruction_details: dict[str, str] | None = None,
        transaction_code: TransactionCode | None = None,
        override_all_restrictions: bool | None = False,
        **kwargs,
    ) -> InboundAuthorisation:
        denomination = denomination or self.default_denomination
        instruction = InboundAuthorisation(
            client_transaction_id=client_transaction_id,
            amount=amount,
            denomination=denomination,
            target_account_id=target_account_id,
            internal_account_id=internal_account_id,
            advice=advice,
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
        )
        committed_postings = [
            # inbound auth => credit PENDING_IN
            Posting(
                credit=True,
                amount=amount,
                denomination=denomination,
                account_id=target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.PENDING_IN,
            ),
        ]
        instruction._set_output_attributes(
            insertion_datetime=kwargs.get("insertion_datetime"),
            value_datetime=kwargs.get("value_datetime", DEFAULT_DATETIME),
            client_batch_id=kwargs.get("client_batch_id"),
            batch_id=kwargs.get("batch_id"),
            committed_postings=committed_postings,
            instruction_id=kwargs.get("instruction_id"),
            unique_client_transaction_id=kwargs.get(
                "unique_client_transaction_id", f"{POSTING_CLIENT_ID}_{client_transaction_id}"
            ),
            client_transaction_id=client_transaction_id,
            own_account_id=kwargs.get("own_account_id", ACCOUNT_ID),
            tside=self.tside,
        )
        return instruction

    def outbound_auth(
        self,
        amount: Decimal,
        client_transaction_id: str = CLIENT_TRANSACTION_ID,
        denomination: str = "",
        target_account_id: str = ACCOUNT_ID,
        internal_account_id: str = DEFAULT_INTERNAL_ACCOUNT,
        advice: bool | None = False,
        instruction_details: dict[str, str] | None = None,
        transaction_code: TransactionCode | None = None,
        override_all_restrictions: bool | None = False,
        **kwargs,
    ) -> OutboundAuthorisation:
        denomination = denomination or self.default_denomination
        instruction = OutboundAuthorisation(
            client_transaction_id=client_transaction_id,
            amount=amount,
            denomination=denomination,
            target_account_id=target_account_id,
            internal_account_id=internal_account_id,
            advice=advice,
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
        )
        committed_postings = [
            # outbound auth => debit PENDING_OUT
            Posting(
                credit=False,
                amount=amount,
                denomination=denomination,
                account_id=target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.PENDING_OUT,
            ),
        ]
        instruction._set_output_attributes(
            insertion_datetime=kwargs.get("insertion_datetime"),
            value_datetime=kwargs.get("value_datetime", DEFAULT_DATETIME),
            client_batch_id=kwargs.get("client_batch_id"),
            batch_id=kwargs.get("batch_id"),
            committed_postings=committed_postings,
            instruction_id=kwargs.get("instruction_id"),
            unique_client_transaction_id=kwargs.get(
                "unique_client_transaction_id", f"{POSTING_CLIENT_ID}_{client_transaction_id}"
            ),
            client_transaction_id=client_transaction_id,
            own_account_id=kwargs.get("own_account_id", ACCOUNT_ID),
            tside=self.tside,
        )
        return instruction

    def inbound_auth_adjust(
        self,
        # adjustment_amount: AdjustmentAmount, # TODO: update to use adjustment amount
        amount: Decimal,
        client_transaction_id: str = CLIENT_TRANSACTION_ID,
        advice: bool | None = False,
        instruction_details: dict[str, str] | None = None,
        transaction_code: TransactionCode | None = None,
        override_all_restrictions: bool | None = False,
        # ----- output values
        _authorised_amount: Decimal | None = None,
        _delta_amount: Decimal | None = None,
        _denomination: str = "",
        _target_account_id: str = ACCOUNT_ID,
        _internal_account_id: str = DEFAULT_INTERNAL_ACCOUNT,
        **kwargs,
    ) -> AuthorisationAdjustment:
        adjustment_amount = AdjustmentAmount(amount=amount)
        instruction = AuthorisationAdjustment(
            client_transaction_id=client_transaction_id,
            adjustment_amount=adjustment_amount,
            advice=advice,
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
        )
        committed_postings = [
            Posting(
                credit=amount > 0,  # credit account if amount > 0
                amount=abs(amount),
                denomination=_denomination or self.default_denomination,
                account_id=_target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.PENDING_IN,  # inbound => PENDING_IN
            ),
        ]
        instruction._set_output_attributes(
            insertion_datetime=kwargs.get("insertion_datetime"),
            value_datetime=kwargs.get("value_datetime", DEFAULT_DATETIME),
            client_batch_id=kwargs.get("client_batch_id"),
            batch_id=kwargs.get("batch_id"),
            committed_postings=committed_postings,
            instruction_id=kwargs.get("instruction_id"),
            unique_client_transaction_id=kwargs.get(
                "unique_client_transaction_id", f"{POSTING_CLIENT_ID}_{client_transaction_id}"
            ),
            client_transaction_id=kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID),
            own_account_id=kwargs.get("own_account_id", ACCOUNT_ID),
            tside=self.tside,
            authorised_amount=kwargs.get("authorised_amount", _authorised_amount),
            delta_amount=kwargs.get("delta_amount", _delta_amount),
            denomination=kwargs.get("denomination", _denomination or self.default_denomination),
            target_account_id=kwargs.get("target_account_id", _target_account_id),
            internal_account_id=kwargs.get("internal_account_id", _internal_account_id),
        )
        return instruction

    def outbound_auth_adjust(
        self,
        # adjustment_amount: AdjustmentAmount, # TODO: update to use adjustment amount
        amount: Decimal,
        client_transaction_id: str = CLIENT_TRANSACTION_ID,
        advice: bool | None = False,
        instruction_details: dict[str, str] | None = None,
        transaction_code: TransactionCode | None = None,
        override_all_restrictions: bool | None = False,
        # ----- output values
        _authorised_amount: Decimal | None = None,
        _delta_amount: Decimal | None = None,
        _denomination: str | None = None,
        _target_account_id: str = ACCOUNT_ID,
        _internal_account_id: str = DEFAULT_INTERNAL_ACCOUNT,
        **kwargs,
    ) -> AuthorisationAdjustment:
        adjustment_amount = AdjustmentAmount(amount=amount)
        instruction = AuthorisationAdjustment(
            client_transaction_id=client_transaction_id,
            adjustment_amount=adjustment_amount,
            advice=advice,
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
        )
        committed_postings = [
            Posting(
                credit=not (amount > 0),  # debit account if amount > 0
                amount=abs(amount),
                denomination=_denomination or self.default_denomination,
                account_id=_target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.PENDING_OUT,  # outbound => PENDING_OUT
            )
        ]
        instruction._set_output_attributes(
            insertion_datetime=kwargs.get("insertion_datetime"),
            value_datetime=kwargs.get("value_datetime", DEFAULT_DATETIME),
            client_batch_id=kwargs.get("client_batch_id"),
            batch_id=kwargs.get("batch_id"),
            committed_postings=committed_postings,
            instruction_id=kwargs.get("instruction_id"),
            unique_client_transaction_id=kwargs.get(
                "unique_client_transaction_id", f"{POSTING_CLIENT_ID}_{client_transaction_id}"
            ),
            client_transaction_id=kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID),
            own_account_id=kwargs.get("own_account_id", ACCOUNT_ID),
            tside=self.tside,
            authorised_amount=kwargs.get("authorised_amount", _authorised_amount),
            delta_amount=kwargs.get("delta_amount", _delta_amount),
            denomination=kwargs.get("denomination", _denomination or self.default_denomination),
            target_account_id=kwargs.get("target_account_id", _target_account_id),
            internal_account_id=kwargs.get("internal_account_id", _internal_account_id),
        )
        return instruction

    def settle_inbound_auth(
        self,
        unsettled_amount: Decimal,
        amount: Decimal | None = None,  # TODO: link with client transaction
        client_transaction_id: str = CLIENT_TRANSACTION_ID,
        final: bool | None = False,
        instruction_details: dict[str, str] | None = None,
        transaction_code: TransactionCode | None = None,
        override_all_restrictions: bool | None = False,
        # ----- output values
        _denomination: str = "",
        _target_account_id: str = ACCOUNT_ID,
        _internal_account_id: str = DEFAULT_INTERNAL_ACCOUNT,
        **kwargs,
    ) -> Settlement:
        amount = amount or unsettled_amount
        pending_amount = unsettled_amount if final else min(amount, unsettled_amount)

        instruction = Settlement(
            client_transaction_id=client_transaction_id,
            amount=amount,
            final=final,
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
            _from_proto=kwargs.get("_from_proto", False),
        )
        committed_postings = [
            Posting(
                # inbound auth is crediting PENDING_IN=> settlement is debiting
                credit=False,
                amount=pending_amount,
                denomination=_denomination or self.default_denomination,
                account_id=_target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.PENDING_IN,
                _from_proto=kwargs.get("_from_proto", False),
            ),
            Posting(
                credit=True,  # settle inbound => True
                amount=amount,
                denomination=_denomination or self.default_denomination,
                account_id=_target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=DEFAULT_PHASE,
                _from_proto=kwargs.get("_from_proto", False),
            ),
        ]
        instruction._set_output_attributes(
            insertion_datetime=kwargs.get("insertion_datetime"),
            value_datetime=kwargs.get("value_datetime", DEFAULT_DATETIME),
            client_batch_id=kwargs.get("client_batch_id"),
            batch_id=kwargs.get("batch_id"),
            committed_postings=committed_postings,
            instruction_id=kwargs.get("instruction_id"),
            unique_client_transaction_id=kwargs.get(
                "unique_client_transaction_id", f"{POSTING_CLIENT_ID}_{client_transaction_id}"
            ),
            client_transaction_id=kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID),
            own_account_id=kwargs.get("own_account_id", ACCOUNT_ID),
            tside=self.tside,
            denomination=kwargs.get("denomination", _denomination or self.default_denomination),
            target_account_id=kwargs.get("target_account_id", _target_account_id),
            internal_account_id=kwargs.get("internal_account_id", _internal_account_id),
        )
        return instruction

    def settle_outbound_auth(
        self,
        unsettled_amount: Decimal,
        amount: Decimal | None = None,  # TODO: link with client transaction
        client_transaction_id: str = CLIENT_TRANSACTION_ID,
        final: bool | None = False,
        instruction_details: dict[str, str] | None = None,
        transaction_code: TransactionCode | None = None,
        override_all_restrictions: bool | None = False,
        # ----- output values
        _denomination: str = "",
        _target_account_id: str = ACCOUNT_ID,
        _internal_account_id: str = DEFAULT_INTERNAL_ACCOUNT,
        **kwargs,
    ) -> Settlement:
        """
        - unsettled_amount: this can be used as the amount if the settlement is final
        and has no amount, or to zero out any pending_in/out phase balances if the
         settlement has an amount > ringfenced amount
        """
        amount = amount or unsettled_amount
        pending_amount = unsettled_amount if final else min(amount, unsettled_amount)
        instruction = Settlement(
            client_transaction_id=client_transaction_id,
            amount=amount,
            final=final,
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
            _from_proto=kwargs.get("_from_proto", False),
        )
        committed_postings = [
            Posting(
                # outbound auth is debiting PENDING_OUT => settlement is credit
                credit=True,
                amount=pending_amount,
                denomination=_denomination or self.default_denomination,
                account_id=_target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.PENDING_OUT,
                _from_proto=kwargs.get("_from_proto", False),
            ),
            Posting(
                credit=False,  # settle outbound => False
                amount=amount,
                denomination=_denomination or self.default_denomination,
                account_id=_target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=DEFAULT_PHASE,
                _from_proto=kwargs.get("_from_proto", False),
            ),
        ]
        client_transaction_id = kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID)
        instruction._set_output_attributes(
            insertion_datetime=kwargs.get("insertion_datetime"),
            value_datetime=kwargs.get("value_datetime", DEFAULT_DATETIME),
            client_batch_id=kwargs.get("client_batch_id"),
            batch_id=kwargs.get("batch_id"),
            committed_postings=committed_postings,
            instruction_id=kwargs.get("instruction_id"),
            unique_client_transaction_id=kwargs.get(
                "unique_client_transaction_id", f"{POSTING_CLIENT_ID}_{client_transaction_id}"
            ),
            client_transaction_id=kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID),
            own_account_id=kwargs.get("own_account_id", ACCOUNT_ID),
            tside=self.tside,
            denomination=kwargs.get("denomination", _denomination or self.default_denomination),
            target_account_id=kwargs.get("target_account_id", _target_account_id),
            internal_account_id=kwargs.get("internal_account_id", _internal_account_id),
        )
        return instruction

    def release_inbound_auth(
        self,
        unsettled_amount: Decimal,
        client_transaction_id: str = CLIENT_TRANSACTION_ID,
        denomination: str = "",
        target_account_id: str = ACCOUNT_ID,
        instruction_details: dict[str, str] | None = None,
        transaction_code: TransactionCode | None = None,
        override_all_restrictions: bool | None = False,
        **kwargs,
    ) -> Release:
        denomination = denomination or self.default_denomination
        instruction = Release(
            client_transaction_id=client_transaction_id,
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
            _from_proto=kwargs.get("_from_proto", False),
        )
        committed_postings = [
            Posting(
                credit=False,  # release inbound => False
                amount=unsettled_amount,
                denomination=denomination,
                account_id=target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.PENDING_IN,  # inbound => PENDING_IN
                _from_proto=kwargs.get("_from_proto", False),
            ),
        ]
        instruction._set_output_attributes(
            insertion_datetime=kwargs.get("insertion_datetime"),
            value_datetime=kwargs.get("value_datetime", DEFAULT_DATETIME),
            client_batch_id=kwargs.get("client_batch_id"),
            batch_id=kwargs.get("batch_id"),
            committed_postings=committed_postings,
            instruction_id=kwargs.get("instruction_id"),
            unique_client_transaction_id=kwargs.get(
                "unique_client_transaction_id", f"{POSTING_CLIENT_ID}_{client_transaction_id}"
            ),
            client_transaction_id=kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID),
            own_account_id=kwargs.get("own_account_id", ACCOUNT_ID),
            tside=self.tside,
            amount=unsettled_amount,
            denomination=denomination,
            target_account_id=target_account_id,
            internal_account_id=kwargs.get("internal_account_id", DEFAULT_INTERNAL_ACCOUNT),
        )
        return instruction

    def release_outbound_auth(
        self,
        unsettled_amount: Decimal,
        client_transaction_id: str = CLIENT_TRANSACTION_ID,
        denomination: str = "",
        target_account_id: str = ACCOUNT_ID,
        instruction_details: dict[str, str] | None = None,
        transaction_code: TransactionCode | None = None,
        override_all_restrictions: bool | None = False,
        **kwargs,
    ) -> Release:
        denomination = denomination or self.default_denomination
        instruction = Release(
            client_transaction_id=client_transaction_id,
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
            _from_proto=kwargs.get("_from_proto", False),
        )
        committed_postings = [
            Posting(
                credit=True,  # release outbound => True
                amount=unsettled_amount,
                denomination=denomination,
                account_id=target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.PENDING_OUT,  # outbound => PENDING_OUT
                _from_proto=kwargs.get("_from_proto", False),
            )
        ]
        instruction._set_output_attributes(
            insertion_datetime=kwargs.get("insertion_datetime"),
            value_datetime=kwargs.get("value_datetime", DEFAULT_DATETIME),
            client_batch_id=kwargs.get("client_batch_id"),
            batch_id=kwargs.get("batch_id"),
            committed_postings=committed_postings,
            instruction_id=kwargs.get("instruction_id"),
            unique_client_transaction_id=kwargs.get(
                "unique_client_transaction_id", f"{POSTING_CLIENT_ID}_{client_transaction_id}"
            ),
            client_transaction_id=kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID),
            own_account_id=kwargs.get("own_account_id", ACCOUNT_ID),
            tside=self.tside,
            amount=unsettled_amount,
            denomination=denomination,
            target_account_id=target_account_id,
            internal_account_id=kwargs.get("internal_account_id", DEFAULT_INTERNAL_ACCOUNT),
        )
        return instruction

    def inbound_hard_settlement(
        self,
        amount: Decimal,
        denomination: str = "",
        target_account_id: str = ACCOUNT_ID,
        internal_account_id: str = DEFAULT_INTERNAL_ACCOUNT,
        advice: bool | None = False,
        instruction_details: dict[str, str] | None = None,
        transaction_code: TransactionCode | None = None,
        override_all_restrictions: bool | None = False,
        **kwargs,
    ) -> InboundHardSettlement:
        denomination = denomination or self.default_denomination
        instruction = InboundHardSettlement(
            amount=amount,
            denomination=denomination,
            target_account_id=target_account_id,
            internal_account_id=internal_account_id,
            advice=advice,
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
        )
        committed_postings = [
            Posting(
                credit=True,  # inbound => True
                amount=amount,
                denomination=denomination,
                account_id=target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=DEFAULT_PHASE,  # hard settlement => COMMITTED
            ),
        ]
        client_transaction_id = kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID)
        instruction._set_output_attributes(
            insertion_datetime=kwargs.get("insertion_datetime"),
            value_datetime=kwargs.get("value_datetime", DEFAULT_DATETIME),
            client_batch_id=kwargs.get("client_batch_id"),
            batch_id=kwargs.get("batch_id"),
            committed_postings=committed_postings,
            instruction_id=kwargs.get("instruction_id"),
            unique_client_transaction_id=kwargs.get(
                "unique_client_transaction_id", f"{POSTING_CLIENT_ID}_{client_transaction_id}"
            ),
            client_transaction_id=kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID),
            own_account_id=kwargs.get("own_account_id", ACCOUNT_ID),
            tside=self.tside,
        )
        return instruction

    def outbound_hard_settlement(
        self,
        amount: Decimal,
        denomination: str = "",
        target_account_id: str = ACCOUNT_ID,
        internal_account_id: str = DEFAULT_INTERNAL_ACCOUNT,
        advice: bool | None = False,
        instruction_details: dict[str, str] | None = None,
        transaction_code: TransactionCode | None = None,
        override_all_restrictions: bool | None = False,
        **kwargs,
    ) -> OutboundHardSettlement:
        denomination = denomination or self.default_denomination
        instruction = OutboundHardSettlement(
            amount=amount,
            denomination=denomination,
            target_account_id=target_account_id,
            internal_account_id=internal_account_id,
            advice=advice,
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
        )
        committed_postings = [
            Posting(
                credit=False,  # outbound => False
                amount=amount,
                denomination=denomination,
                account_id=target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=DEFAULT_PHASE,  # hard settlement => COMMITTED
            ),
        ]
        client_transaction_id = kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID)
        instruction._set_output_attributes(
            insertion_datetime=kwargs.get("insertion_datetime"),
            value_datetime=kwargs.get("value_datetime", DEFAULT_DATETIME),
            client_batch_id=kwargs.get("client_batch_id"),
            batch_id=kwargs.get("batch_id"),
            committed_postings=committed_postings,
            instruction_id=kwargs.get("instruction_id"),
            unique_client_transaction_id=kwargs.get(
                "unique_client_transaction_id", f"{POSTING_CLIENT_ID}_{client_transaction_id}"
            ),
            client_transaction_id=client_transaction_id,
            own_account_id=kwargs.get("own_account_id", ACCOUNT_ID),
            tside=self.tside,
        )
        return instruction

    def inbound_transfer(
        self,
        amount: Decimal,
        denomination: str = "",
        debtor_target_account_id: str = DEFAULT_INTERNAL_ACCOUNT,
        creditor_target_account_id: str = ACCOUNT_ID,
        instruction_details: dict[str, str] | None = None,
        transaction_code: TransactionCode | None = None,
        override_all_restrictions: bool | None = False,
        **kwargs,
    ) -> Transfer:
        denomination = denomination or self.default_denomination
        instruction = Transfer(
            amount=amount,
            denomination=denomination,
            debtor_target_account_id=debtor_target_account_id,
            creditor_target_account_id=creditor_target_account_id,
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
        )
        client_transaction_id = kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID)
        committed_postings = [
            Posting(
                credit=True,  # inbound => True
                amount=amount,
                denomination=denomination,
                account_id=creditor_target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=DEFAULT_PHASE,  # transfer => COMMITTED
            ),
        ]
        instruction._set_output_attributes(
            insertion_datetime=kwargs.get("insertion_datetime"),
            value_datetime=kwargs.get("value_datetime", DEFAULT_DATETIME),
            client_batch_id=kwargs.get("client_batch_id"),
            batch_id=kwargs.get("batch_id"),
            committed_postings=committed_postings,
            instruction_id=kwargs.get("instruction_id"),
            unique_client_transaction_id=kwargs.get(
                "unique_client_transaction_id", f"{POSTING_CLIENT_ID}_{client_transaction_id}"
            ),
            client_transaction_id=kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID),
            own_account_id=kwargs.get("own_account_id", ACCOUNT_ID),
            tside=self.tside,
        )
        return instruction

    def outbound_transfer(
        self,
        amount: Decimal,
        denomination: str = "",
        debtor_target_account_id: str = ACCOUNT_ID,
        creditor_target_account_id: str = DEFAULT_INTERNAL_ACCOUNT,
        instruction_details: dict[str, str] | None = None,
        transaction_code: TransactionCode | None = None,
        override_all_restrictions: bool | None = False,
        **kwargs,
    ) -> Transfer:
        denomination = denomination or self.default_denomination
        instruction = Transfer(
            amount=amount,
            denomination=denomination,
            debtor_target_account_id=debtor_target_account_id,
            creditor_target_account_id=creditor_target_account_id,
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
        )
        committed_postings = [
            Posting(
                credit=False,  # outbound => False
                amount=amount,
                denomination=denomination,
                account_id=debtor_target_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=DEFAULT_PHASE,  # transfer => COMMITTED
            )
        ]
        client_transaction_id = kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID)
        instruction._set_output_attributes(
            insertion_datetime=kwargs.get("insertion_datetime"),
            value_datetime=kwargs.get("value_datetime", DEFAULT_DATETIME),
            client_batch_id=kwargs.get("client_batch_id"),
            batch_id=kwargs.get("batch_id"),
            committed_postings=committed_postings,
            instruction_id=kwargs.get("instruction_id"),
            unique_client_transaction_id=kwargs.get(
                "unique_client_transaction_id", f"{POSTING_CLIENT_ID}_{client_transaction_id}"
            ),
            client_transaction_id=kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID),
            own_account_id=kwargs.get("own_account_id", ACCOUNT_ID),
            tside=self.tside,
        )
        return instruction

    def custom_instruction(
        self,
        postings: list[Posting],
        instruction_details: dict[str, str] | None = None,
        transaction_code: TransactionCode | None = None,
        override_all_restrictions: bool | None = False,
        **kwargs,
    ) -> CustomInstruction:
        instruction = CustomInstruction(
            postings=postings,
            instruction_details=instruction_details,
            transaction_code=transaction_code,
            override_all_restrictions=override_all_restrictions,
        )
        client_transaction_id = kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID)
        instruction._set_output_attributes(
            insertion_datetime=kwargs.get("insertion_datetime"),
            value_datetime=kwargs.get("value_datetime", DEFAULT_DATETIME),
            client_batch_id=kwargs.get("client_batch_id"),
            batch_id=kwargs.get("batch_id"),
            committed_postings=postings,
            instruction_id=kwargs.get("instruction_id"),
            unique_client_transaction_id=kwargs.get(
                "unique_client_transaction_id", f"{POSTING_CLIENT_ID}_{client_transaction_id}"
            ),
            client_transaction_id=kwargs.get("client_transaction_id", CLIENT_TRANSACTION_ID),
            own_account_id=kwargs.get("own_account_id", ACCOUNT_ID),
            tside=self.tside,
        )
        return instruction

    # Balance helpers
    def balance(
        self,
        *,
        net: Decimal | None = None,
        debit: Decimal | None = None,
        credit: Decimal | None = None,
    ) -> Balance:
        """
        Given a net, or a debit/credit pair, return an equivalent Balance object
        Direction of net is derived from Tside of account (asset vs. liability).
        Only currently works for positive net values.
        :param net: If populated, debit and credit parameters are ignored. For Liability tside, the
        debit is set to 0 and credit set to net. For Asset tside, the debit it set to net and credit
        set to 0
        :param debit: Only considered if net is not populated. If so, credit must also be populated
        and net is derived as debit - credit (tside Asset) or credit - debit (tside Liability)
        :param credit: Only considered if net is not populated. If so, debit must also be populated
        and net is derived as debit - credit (tside Asset) or credit - debit (tside Liability)
        """
        if net is None:
            if credit is None or debit is None:
                raise ValueError(
                    "Cannot create balance with net `None` and credit/debit also `None`"
                )
            net = (
                Decimal(credit) - Decimal(debit)
                if (self.tside == Tside.LIABILITY)
                else Decimal(debit) - Decimal(credit)
            )

        else:
            net = Decimal(net)
            if self.tside == Tside.LIABILITY:
                credit = net
                debit = Decimal(0)
            else:
                credit = Decimal(0)
                debit = net
        return Balance(debit=debit, credit=credit, net=net)

    def balance_coordinate(
        self,
        *,
        account_address: str = DEFAULT_ADDRESS,
        denomination: str = "",
        phase: Phase = DEFAULT_PHASE,
        asset: str = DEFAULT_ASSET,
    ) -> BalanceCoordinate:
        denomination = denomination if denomination else self.default_denomination
        return BalanceCoordinate(
            account_address=account_address,
            asset=asset,
            denomination=denomination,
            phase=phase,
        )

    def construct_balance_timeseries(
        self,
        *,
        dt: datetime,
        net: Decimal | None = None,
        debit: Decimal | None = None,
        credit: Decimal | None = None,
    ) -> BalanceTimeseries:
        """
        Balance timeseries version of the balance() helper - making a timeseries with 1 time point

        :param datetime dt: timestamps of the balances present in your desired timeseries
        :param net: net value of the balance, defaults to None
        :param debit: debit value of the balance, defaults to None
        :param credit: credit value of the balance, defaults to None
        :return BalanceTimeseries: Simple BalanceTimeseries with 1 balance at 1 time point
        """
        return BalanceTimeseries([(dt, self.balance(net=net, debit=debit, credit=credit))])


class FeatureTest(ContractTest):
    # Override tside since features should not need them, but if a specific test needs tside
    # then this can be set at the class level
    tside = None  # type: ignore
