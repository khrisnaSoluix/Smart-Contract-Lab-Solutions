from abc import abstractmethod
from datetime import datetime
from typing import Optional, Union

from . import types as supervisor_contract_types
from ...version_3100.supervisor_contracts import lib as v3100_lib
from ..common import lib as common_lib
from ....utils import symbols, types_utils
from functools import lru_cache

types_registry = supervisor_contract_types.types_registry

ALLOWED_BUILTINS = common_lib.ALLOWED_BUILTINS


class VaultFunctionsABC(v3100_lib.VaultFunctionsABC):
    @abstractmethod
    def update_event_type(
        self,
        event_type: str,
        schedule: Optional[supervisor_contract_types.EventTypeSchedule] = None,
        end_datetime: Optional[datetime] = None,
        schedule_method: Optional[supervisor_contract_types.EndOfMonthSchedule] = None,
        skip: Optional[Union[bool, supervisor_contract_types.ScheduleSkip]] = None,
    ):
        pass

    @classmethod
    @lru_cache()

    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        spec = super()._spec(language_code)

        spec.public_methods["update_event_type"].args["skip"] = types_utils.ValueSpec(
            name="skip",
            type="Optional[Union[bool, ScheduleSkip]]",
            docstring="""
                An optional flag to skip a schedule indefinitely (True), unskip a
                Schedule (False), or to skip until a specified time (ScheduleSkip).
                **Only available in version 3.11.0+**
            """,
        )
        spec.public_methods["update_event_type"].examples.append(
            types_utils.Example(
                title="Vault update_event_type usage example using ScheduleSkip",
                code="""
                    vault.update_event_type(
                        event_type="TEST_EVENT_1",
                        skip=ScheduleSkip(
                            end=effective_date + timedelta(days=1)
                        )
                    )
                """,
            )
        )
        return spec
