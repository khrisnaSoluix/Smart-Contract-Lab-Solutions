# standard libs
from datetime import datetime
from typing import Mapping, Optional, Union
from zoneinfo import ZoneInfo

# contracts api
from contracts_api.versions.version_400.common.types import (
    AuthorisationAdjustment,
    BalanceCoordinate,
    BalancesObservation,
    BalanceTimeseries,
    CalendarEvents,
    ClientTransaction,
    CustomInstruction,
    FlagTimeseries,
    InboundAuthorisation,
    InboundHardSettlement,
    OutboundAuthorisation,
    OutboundHardSettlement,
    ParameterTimeseries,
    PostPostingHookResult,
    PrePostingHookResult,
    Release,
    ScheduledEventHookResult,
    Settlement,
    Transfer,
    Tside,
)


class SmartContractVault:
    _account_id: str
    _tside: Tside
    _events_timezone: ZoneInfo

    @property
    def tside(self) -> Tside:
        return self._tside

    @property
    def account_id(self) -> str:
        return self._account_id

    @property
    def events_timezone(self) -> ZoneInfo:
        return self._events_timezone

    def get_last_execution_datetime(self, *, event_type: str) -> Optional[datetime]:
        ...

    def get_posting_instructions(
        self, *, fetcher_id: str
    ) -> list[
        Union[
            AuthorisationAdjustment,
            CustomInstruction,
            InboundAuthorisation,
            InboundHardSettlement,
            OutboundAuthorisation,
            OutboundHardSettlement,
            Release,
            Settlement,
            Transfer,
        ]
    ]:
        ...

    def get_client_transactions(self, *, fetcher_id: str) -> dict[str, ClientTransaction]:
        ...

    def get_account_creation_datetime(self) -> datetime:
        ...

    def get_balances_timeseries(
        self, *, fetcher_id: str
    ) -> Mapping[BalanceCoordinate, BalanceTimeseries]:
        ...

    def get_hook_execution_id(self) -> str:
        ...

    def get_parameter_timeseries(self, *, name: str) -> ParameterTimeseries:
        ...

    def get_flag_timeseries(self, *, flag: str) -> FlagTimeseries:
        ...

    def get_permitted_denominations(self) -> list[str]:
        ...

    def get_calendar_events(self, *, calendar_ids: list[str]) -> CalendarEvents:
        ...

    def get_balances_observation(self, *, fetcher_id: str) -> BalancesObservation:
        ...


class SuperviseeContractVault(SmartContractVault):
    def get_alias(self) -> str:
        ...

    def get_hook_result(
        self,
    ) -> Union[PostPostingHookResult, PrePostingHookResult, ScheduledEventHookResult]:
        ...

    # override standard vault methods due to ODF restrictions in supervisors
    # ignore mypy warning for 'Signature incompatible with supertype'
    def get_balances_timeseries(  # type: ignore
        self, *, fetcher_id: Optional[str] = None
    ) -> Mapping[BalanceCoordinate, BalanceTimeseries]:
        ...

    def get_posting_instructions(  # type: ignore
        self,
    ) -> list[
        Union[
            AuthorisationAdjustment,
            CustomInstruction,
            InboundAuthorisation,
            InboundHardSettlement,
            OutboundAuthorisation,
            OutboundHardSettlement,
            Release,
            Settlement,
            Transfer,
        ]
    ]:
        ...

    def get_client_transactions(  # type: ignore
        self,
    ) -> dict[str, ClientTransaction]:
        ...


class SupervisorContractVault:
    plan_id: str
    supervisees: dict[str, SuperviseeContractVault]

    def get_hook_execution_id(self) -> str:
        ...

    def get_calendar_events(self, *, calendar_ids: list[str]) -> CalendarEvents:
        ...

    def get_plan_opening_datetime(self) -> datetime:
        ...


# flake8: noqa
