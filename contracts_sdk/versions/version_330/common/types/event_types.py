from functools import lru_cache

from .....utils import exceptions
from .....utils import types_utils
from .....utils import symbols


class EventTypesGroup:
    def __init__(self, *, name, event_types_order):
        self._spec().assert_constructor_args(
            self._registry, {"name": name, "event_types_order": event_types_order}
        )

        if len(event_types_order) < 2:
            raise exceptions.InvalidSmartContractError(
                f"An EventTypesGroup must have at least two event types"
            )

        self.name = name
        self.event_types_order = event_types_order

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return types_utils.ClassSpec(
            name="EventTypesGroup",
            docstring="""
**Only available in version 3.3+.**
A [group of event types](/reference/scheduler/#concepts-schedule_groups) that defines
the scheduling order for events in the group. If any EventTypesGroup is
defined in a Smart Contract, a list of [EventType](#classes-EventType)s must also be defined.
Every event type from a group must be defined in the event types list.
EventTypesGroups are unique for each account. Events associated with different
accounts are **NOT** added to the same group even if the EventTypesGroup names
match.
""",
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new EventTypesGroup",
                args=cls._public_attributes(language_code),
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
                    The name of the EventTypesGroup. Names have to be unique within a Smart
                    Contract.
                """,
            ),
            types_utils.ValueSpec(
                name="event_types_order",
                type="List[str]",
                docstring="""
                    A list of string [EventType](#classes-EventType) names that belong to a group.
                    A group consists of at least two [EventType](#classes-EventType)s.
                    An [EventType](#classes-EventType) cannot belong to more than one group.
                    This list defines the order of [EventType](#classes-EventType)s inside a group.
                    Any [EventType](#classes-EventType)s grouped together are executed based on the
                    order of this list.
                """,
            ),
        ]
