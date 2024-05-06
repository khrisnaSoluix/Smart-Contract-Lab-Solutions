from abc import abstractmethod
from functools import lru_cache
from typing import List

from . import types as smart_contract_types
from ....utils import symbols, types_utils
from ...version_360.smart_contracts import lib as v360_lib
from ..common import lib as common_lib


types_registry = smart_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v360_lib.VaultFunctionsABC):
    @abstractmethod
    def get_calendar_events(self, *, calendar_ids: List[str]):
        pass

    @abstractmethod
    def make_internal_transfer_instructions(
        self,
        *,
        amount,
        denomination,
        client_transaction_id,
        from_account_id,
        from_account_address=None,
        to_account_id,
        to_account_address=None,
        pics=None,
        override_all_restrictions=False,
        instruction_details=None,
        transaction_code=None,
        asset=symbols.DEFAULT_ASSET,
    ):
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
        key = "make_internal_transfer_instructions"
        arg = "transaction_code"
        spec.public_methods[key].args[arg] = types_utils.ValueSpec(
            name="transaction_code",
            type="Optional[TransactionCode]",
            docstring="""
                Optional ``[./TransactionCode]`` attribute to be attached to the created PostingInstruction.
                **Only available in version 3.7.0+**.
            """,  # noqa E501
        )

        return spec
