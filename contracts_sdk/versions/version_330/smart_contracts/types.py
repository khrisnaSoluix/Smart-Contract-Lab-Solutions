from functools import lru_cache

from ..common.types import ROUND_CEILING, ROUND_DOWN, ROUND_HALF_EVEN, ROUND_05UP, EventTypesGroup
from ...version_320.smart_contracts.types import *  # noqa: F401, F403
from ...version_320.smart_contracts import types as types320
from ....utils import types_utils
from ....utils import symbols


class EventType:
    def __init__(self, *, name, scheduler_tag_ids=None):
        self._spec().assert_constructor_args(
            self._registry, {"name": name, "scheduler_tag_ids": scheduler_tag_ids}
        )

        self.name = name
        self.scheduler_tag_ids = scheduler_tag_ids

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="EventType",
            docstring="""
                **Only available in version 3.3+.**
                Each scheduled event in a Smart Contract has an event type associated with it.
                Each event type must have a unique name within each Smart Contract and can have
                optional Scheduler tags. Each Smart Contract must include a list of all
                [EventType](#classes-EventType)s included in its execution_schedules hook.
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new EventType", args=cls._public_attributes(language_code)
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="name",
                type="str",
                docstring="""
                    The name of the [EventType](#classes-EventType). This name will be the same as
                    the name defined in the [execution_schedules](../../smart_contracts_api_reference3XX/hooks/#execution_schedules)
                    hook.
                """,
            ),
            types_utils.ValueSpec(
                name="scheduler_tag_ids",
                type="Optional[List[str]]",
                docstring="""
                    An optional list of string ids for the
                    [scheduler tags](/api/core_api/#Scheduler-ScheduleTag) of an
                    [EventType](#classes-EventType). The tags must be created in the Scheduler
                    before they are referenced in a Smart Contract. The tag IDs are global in Vault
                    and must exactly match the tag IDs created in the Scheduler.
                    [EventType](#classes-EventType)s in different contracts with the same tag will
                    be linked together. Defaults to no tags if a tag ID is not provided.
                """,
            ),
        ]


def types_registry():
    TYPES = types320.types_registry()
    TYPES["ROUND_CEILING"] = ROUND_CEILING
    TYPES["ROUND_DOWN"] = ROUND_DOWN
    TYPES["ROUND_HALF_EVEN"] = ROUND_HALF_EVEN
    TYPES["ROUND_05UP"] = ROUND_05UP
    TYPES["EventType"] = EventType
    TYPES["EventTypesGroup"] = EventTypesGroup
    return TYPES
