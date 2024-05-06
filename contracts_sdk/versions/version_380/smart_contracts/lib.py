from abc import abstractmethod
from datetime import datetime
from functools import lru_cache
from typing import Optional

from . import types as smart_contract_types
from ....utils import symbols, types_utils
from ...version_370.smart_contracts import lib as v370_lib
from ..common import lib as common_lib


types_registry = smart_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v370_lib.VaultFunctionsABC):
    @abstractmethod
    def update_event_type(
        self,
        event_type: str,
        schedule: Optional[smart_contract_types.EventTypeSchedule] = None,
        end_datetime: Optional[datetime] = None,
    ):
        pass

    @abstractmethod
    def amend_schedule(self, *, event_type, new_schedule):
        pass

    @abstractmethod
    def remove_schedule(self, *, event_type):
        pass

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        spec = super()._spec(language_code)
        spec.public_methods["update_event_type"] = types_utils.MethodSpec(
            name="update_event_type",
            docstring="""
                Updates the `event_type` for an account.
                Can only be called once per hook execution for each `event_type`.
                **Only available in version 3.8.0+**
            """,
            args=[
                types_utils.ValueSpec(
                    name="event_type",
                    type="str",
                    docstring="The `event_type` that is to be modified.",
                ),
                types_utils.ValueSpec(
                    name="schedule",
                    type="Optional[EventTypeSchedule]",
                    docstring="Optional [EventTypeSchedule](#classes-EventTypeSchedule).",
                ),
                types_utils.ValueSpec(
                    name="end_datetime",
                    type="Optional[datetime]",
                    docstring=(
                        "Optional datetime representing when the "
                        "schedule should stop executing. Must have the same timezone "
                        "localization as the Contract."
                        "Note that once the end_datetime has been reached, "
                        "the schedule can **no longer** be updated or re-enabled."
                    ),
                ),
            ],
            examples=[
                types_utils.Example(
                    title="The Vault update event type usage example",
                    code="""
                        vault.update_event_type(
                            event_type='EVENT_NAME',
                            schedule=EventTypeSchedule(
                                minute='*/2', # every 2 minutes
                            ),
                            end_datetime=vault.get_account_creation_date()
                        )
                    """,
                )
            ],
        )
        return spec
