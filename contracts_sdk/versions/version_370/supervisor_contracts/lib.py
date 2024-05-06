from abc import abstractmethod
from functools import lru_cache
from typing import List

from . import types as supervisor_contract_types
from ....utils import symbols, types_utils
from ...version_360.supervisor_contracts import lib as v360_lib
from ..common import lib as common_lib


types_registry = supervisor_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v360_lib.VaultFunctionsABC):
    @abstractmethod
    def get_calendar_events(self, *, calendar_ids: List[str]):
        pass

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        spec = super()._spec(language_code)
        spec.public_methods["get_calendar_events"] = types_utils.MethodSpec(
            name="get_calendar_events",
            docstring="""
                Returns a [CalendarEvents](../types/#classes-CalendarEvents) object with the
                chronologically ordered list of [CalendarEvent](../types/#classes-CalendarEvent)
                that exist in the Vault calendars with the given `calendar_ids`. These
                `calendar_ids` have to be requested using the hook '@requires' decorator.
                **Only available in version 3.7+.**
            """,
            args=[
                types_utils.ValueSpec(
                    name="calendar_ids", type="List[str]", docstring="List of Calendar Ids"
                ),
            ],
            return_value=types_utils.ReturnValueSpec(
                docstring="""
                    The chronologically ordered list of
                    [CalendarEvent](../types/#classes-CalendarEvent) objects.
                """,
                type="CalendarEvents",
            ),
            examples=[
                types_utils.Example(
                    title="The Vault calendar usage example",
                    code="""
                    @requires(calendar=["WEEKENDS", "BANK_HOLIDAYS", "PROMOTION_DAYS"])
                    def execution_schedules():
                        vault.get_calendar_events(calendar_ids=["WEEKENDS", "BANK_HOLIDAYS"])
                    """,
                )
            ],
        )
        return spec
