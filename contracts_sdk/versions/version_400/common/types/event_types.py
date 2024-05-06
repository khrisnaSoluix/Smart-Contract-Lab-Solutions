from datetime import datetime
from functools import lru_cache
from typing import Optional, Union, List, Tuple

from .schedules import EndOfMonthSchedule
from .....utils import exceptions
from .....utils import symbols
from .....utils import types_utils
from .....utils.timezone_utils import validate_dateime_is_timezone_aware


class EventTypesGroup:
    def __init__(self, *, name: str, event_types_order: List[str]):
        self.name = name
        self.event_types_order = event_types_order
        self._validate_attributes()

    def _validate_attributes(self):
        if self.name is None or self.name == "":
            raise exceptions.InvalidSmartContractError("EventTypesGroup 'name' must be populated")

        types_utils.get_iterator(
            self.event_types_order, "str", "event_types_order", check_empty=True
        )
        if len(self.event_types_order) < 2:
            raise exceptions.InvalidSmartContractError(
                "An EventTypesGroup must have at least two event types"
            )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        docstring = """
            A [group of event types](/reference/scheduler/#concepts-schedule_groups) that defines
            the scheduling order for events in the group. If any EventTypesGroup is
            defined in a Smart Contract, a list of
            [SmartContractEventType](#classes-SmartContractEventType)s must also be defined.
            Every event type from a group must be defined in the event types list.
            EventTypesGroups are unique for each account. Events associated with different
            accounts are **NOT** added to the same group even if the EventTypesGroup names
            match.

            Any events within an EventTypesGroup that are supervised with
            [flexible supervision](/reference/contracts/supervisor_overview/#flexible_supervision)
            will no longer be considered a part of that EventTypesGroup. This means that:
            * Supervised events are **not** guaranteed to be executed in the order
             specified by the original EventTypesGroup. However, unsupervised events are
             guaranteed to be executed in the specified order.
            * Vault skips the original event (defined in the Smart Contract) and the Supervisor
             Contract event runs instead. Since an account is not aware of whether it is being
             supervised, the original event will report a success and the next event
             in the EventTypesGroup will be triggered immediately
             (regardless of whether the Supervisor Contract event has run).
        """  # noqa: E501

        return types_utils.ClassSpec(
            name="EventTypesGroup",
            docstring=docstring,
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
                    A list of string [SmartContractEventType](#classes-SmartContractEventType) names
                    that belong to a group. A group consists of at least two
                    [SmartContractEventType](#classes-SmartContractEventType)s. A
                    [SmartContractEventType](#classes-SmartContractEventType) cannot belong to more
                    than one group. This list defines the order of
                    [SmartContractEventType](#classes-SmartContractEventType)s inside a group.
                    Any [SmartContractEventType](#classes-SmartContractEventType)s grouped together
                    are executed based on the order of this list.
                    Note: in a Supervisor Contract, Event Types are of type
                    [SupervisorContractEventType](#classes-SupervisorContractEventType).
                """,
            ),
        ]


class ScheduleExpression:
    def __init__(
        self,
        *,
        second: Optional[Union[str, int]] = None,
        minute: Optional[Union[str, int]] = None,
        hour: Optional[Union[str, int]] = None,
        day_of_week: Optional[Union[str, int]] = None,
        day: Optional[Union[str, int]] = None,
        month: Optional[Union[str, int]] = None,
        year: Optional[Union[str, int]] = None,
    ):

        self.day = day
        self.day_of_week = day_of_week
        self.hour = hour
        self.minute = minute
        self.second = second
        self.month = month
        self.year = year
        self._validate_attributes()

    def _validate_attributes(self):
        types_utils.validate_type(
            self.second,
            (int, str),
            prefix="second",
            is_optional=True,
            check_empty=True,
        )
        types_utils.validate_type(
            self.minute,
            (int, str),
            prefix="minute",
            is_optional=True,
            check_empty=True,
        )
        types_utils.validate_type(
            self.hour,
            (int, str),
            prefix="hour",
            is_optional=True,
            check_empty=True,
        )
        types_utils.validate_type(
            self.day_of_week,
            (int, str),
            prefix="day_of_week",
            is_optional=True,
            check_empty=True,
        )
        types_utils.validate_type(
            self.day,
            (int, str),
            prefix="day",
            is_optional=True,
            check_empty=True,
        )
        types_utils.validate_type(
            self.month,
            (int, str),
            prefix="month",
            is_optional=True,
            check_empty=True,
        )
        types_utils.validate_type(
            self.year,
            (int, str),
            prefix="year",
            is_optional=True,
            check_empty=True,
        )
        if not any(
            attr is not None
            for attr in [
                self.day,
                self.day_of_week,
                self.hour,
                self.minute,
                self.second,
                self.month,
                self.year,
            ]
        ):
            raise exceptions.InvalidSmartContractError("Empty ScheduleExpression not allowed")

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="day", type="Optional[Union[str, int]]", docstring="Day of the month (1-31)."
            ),
            types_utils.ValueSpec(
                name="day_of_week",
                type="Optional[Union[str, int]]",
                docstring="Day of the week (0-6 or mon-sun).",
            ),
            types_utils.ValueSpec(
                name="hour", type="Optional[Union[str, int]]", docstring="Hour (0-23)."
            ),
            types_utils.ValueSpec(
                name="minute", type="Optional[Union[str, int]]", docstring="Minute (0-59)."
            ),
            types_utils.ValueSpec(
                name="second", type="Optional[Union[str, int]]", docstring="Second (0-59)."
            ),
            types_utils.ValueSpec(
                name="month", type="Optional[Union[str, int]]", docstring="Month (1-12)."
            ),
            types_utils.ValueSpec(
                name="year", type="Optional[Union[str, int]]", docstring="Year (4-digit year)."
            ),
        ]

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ScheduleExpression",
            # TODO: look into rearranging docstring in order to remove E501
            docstring=(
                "The schedule definition associated with an Event Type. All schedule definition "
                "attributes must be based on the `events_timezone` field defined in the "
                "[Smart](../../smart_contracts_api_reference4XX/metadata/#events_timezone) and "
                "[Supervisor](../../supervisor_contracts_api_reference4XX/metadata/#events_timezone) "  # noqa: E501
                "Contract metadata. The allowed keys and values can be seen "
                "[here](https://apscheduler.readthedocs.io/en/latest/modules/triggers/cron.html)."
            ),
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring=(
                    "Constructs a new ScheduleExpression. At least one of the optional attributes "
                    "must be provided."
                ),
                args=cls._public_attributes(language_code),
            ),
        )


class ScheduleSkip:
    def __init__(self, *, end: datetime, _from_proto: bool = False):
        self.end = end
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        if self.end is None:
            raise exceptions.InvalidSmartContractError("ScheduleSkip 'end' must be populated")
        types_utils.validate_type(self.end, datetime)
        validate_dateime_is_timezone_aware(
            self.end,
            "end",
            "ScheduleSkip",
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return types_utils.ClassSpec(
            name="ScheduleSkip",
            docstring="""
                Defines the skip period for a Schedule.
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new ScheduleSkip object.",
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
                name="end",
                type="datetime",
                # TODO: look into rearranging docstring in order to remove E501
                docstring=(
                    "The local datetime until which the Schedule will be skipped. "
                    "Must be timezone aware using the ZoneInfo class and use the "
                    "same timezone as the `events_timezone` field defined in the "
                    "[Smart](../../smart_contracts_api_reference4XX/metadata/#events_timezone) or "
                    "[Supervisor](../../supervisor_contracts_api_reference4XX/metadata/#events_timezone) "  # noqa: E501
                    "Contract metadata."
                ),
            )
        ]


class ScheduledEvent:
    def __init__(
        self,
        *,
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None,
        expression: Optional[ScheduleExpression] = None,
        schedule_method: Optional[EndOfMonthSchedule] = None,
        skip: Optional[Union[bool, ScheduleSkip]] = False,
        _from_proto: bool = False,
    ):
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime
        self.expression = expression
        self.schedule_method = schedule_method
        self.skip = skip
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        # None is only allowed for existing scheduled events returned via `conversion_hook`.
        # This is validated in the private subclass of the ScheduledEvent.
        types_utils.validate_type(
            self.start_datetime,
            datetime,
            is_optional=True,
            hint="datetime",
            prefix="ScheduledEvent.start_datetime",
        )
        if self.start_datetime is not None:
            validate_dateime_is_timezone_aware(
                self.start_datetime,
                "start_datetime",
                "ScheduledEvent",
            )
        types_utils.validate_type(
            self.end_datetime,
            datetime,
            is_optional=True,
            hint="datetime",
            prefix="ScheduledEvent.end_datetime",
        )
        if self.end_datetime is not None:
            validate_dateime_is_timezone_aware(
                self.end_datetime,
                "end_datetime",
                "ScheduledEvent",
            )
        types_utils.validate_type(
            self.expression,
            ScheduleExpression,
            is_optional=True,
            hint="ScheduleExpression",
            prefix="ScheduledEvent.expression",
        )
        types_utils.validate_type(
            self.schedule_method,
            EndOfMonthSchedule,
            is_optional=True,
            hint="EndOfMonthSchedule",
            prefix="ScheduledEvent.schedule_method",
        )
        types_utils.validate_type(
            self.skip,
            (bool, ScheduleSkip),
            is_optional=True,
            hint="Union[bool, ScheduleSkip]",
            prefix="ScheduledEvent.skip",
        )

        if not self.skip:
            if not self.end_datetime and not self.expression and not self.schedule_method:
                raise exceptions.InvalidSmartContractError(
                    "ScheduledEvent must have an end_datetime, expression, schedule_method "
                    "or skip set"
                )
            if self.expression and self.schedule_method:
                raise exceptions.InvalidSmartContractError(
                    "ScheduledEvent must not have both expression and schedule_method set"
                )
            if not self.expression and not self.schedule_method:
                raise exceptions.InvalidSmartContractError(
                    "ScheduledEvent must have exactly one of expression or schedule_method set"
                )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ScheduledEvent",
            docstring="The native representation of a schedule which an event will adhere to.",
            public_attributes=cls._public_attributes(language_code),  # noqa SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new ScheduledEvent object.",
                args=cls._public_attributes(language_code),  # noqa SLF001
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="start_datetime",
                type="Optional[datetime]",
                docstring="""
                    The datetime from which the schedule will be effective.
                    Must be timezone-aware using the `ZoneInfo` class and use the same timezone as
                    the `events_timezone` metadata defined in the Smart or Supervisor Contract.
                    Note that the `start_datetime` is required for any new ScheduledEvents returned
                    by `activation_hook` or `conversion_hook`.
                    However, the `start_datetime` for existing ScheduledEvents is ignored
                    in the `conversion_hook`, so this datetime must be set to None or remain
                    unchanged as any other value will result in an error.
                    Note that the `start_datetime` cannot be before a hook `effective_datetime`
                    for new `event_types` returned in the account or plan `activation_hook`
                    and `conversion_hook`.
                    """,
            ),
            types_utils.ValueSpec(
                name="end_datetime",
                type="Optional[datetime]",
                docstring="""
                    The datetime until which the schedule will be effective.
                    Must be a timezone-aware UTC datetime using the ZoneInfo class.
                    """,
            ),
            types_utils.ValueSpec(
                name="expression",
                type="Optional[ScheduleExpression]",
                docstring="""
                    The cron expression defining the schedule, represented as a native object.
                    Exactly one of `expression` or `schedule_method` must be populated.
                """,
            ),
            types_utils.ValueSpec(
                name="schedule_method",
                type="Optional[EndOfMonthSchedule]",
                docstring="""
                    The schedule definition for a recurring monthly event, represented as a
                    native object. Exactly one of `expression` or `schedule_method` must be
                    populated.
                """,
            ),
            types_utils.ValueSpec(
                name="skip",
                type="Optional[Union[bool, ScheduleSkip]]",
                docstring="""
                    Skip a schedule until a given datetime. If set to `True`, the schedule will
                    be skipped indefinitely until this field is updated.
                """,
            ),
        ]


class EventType:
    def __init__(self, *, name: str, scheduler_tag_ids: Optional[List[str]] = None):
        self.name = name
        self.scheduler_tag_ids = scheduler_tag_ids
        self._validate_attributes()

    def _validate_attributes(self):
        if self.name is None or self.name == "":
            raise exceptions.InvalidSmartContractError(f"{repr(self)} 'name' must be populated")

        if self.scheduler_tag_ids:
            iterator = types_utils.get_iterator(self.scheduler_tag_ids, "str", "scheduler_tag_ids")
            for item in iterator:
                types_utils.validate_type(item, str, hint="str")

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="EventType",
            docstring="""
                Each scheduled event in a Smart Contract has an event type associated with it.
                Each event type must have a unique name within each Smart Contract and can have
                optional Scheduler tags. Each Smart Contract must include a list of all
                [SmartContractEventType](#classes-SmartContractEventType)s included in its
                [activation_hook](../../smart_contracts_api_reference4XX/hooks/#activation_hook) and
                [conversion_hook](../../smart_contracts_api_reference4XX/hooks/#conversion_hook).
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
                    The name of the Event Type. This name will be the same as the name defined in
                    [activation_hook](../../smart_contracts_api_reference4XX/hooks/#activation_hook) or
                    [conversion_hook](../../smart_contracts_api_reference4XX/hooks/#conversion_hook).
                """,  # noqa: E501
            ),
            types_utils.ValueSpec(
                name="scheduler_tag_ids",
                type="Optional[List[str]]",
                docstring="""
                    An optional list of string ids for the
                    [scheduler tags](/api/core_api/#Scheduler-ScheduleTag) of an
                    Event Type. The tags must be created in the Scheduler
                    before they are referenced in a Smart Contract. The tag IDs are global in Vault
                    and must exactly match the tag IDs created in the Scheduler.
                    Event Types in different contracts with the same tag will
                    be linked together. Defaults to no tags if a tag ID is not provided.
                """,
            ),
        ]


class SmartContractEventType(EventType):
    def __repr__(self) -> str:
        return "SmartContractEventType"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SmartContractEventType",
            docstring="""
                Each scheduled event in a Smart Contract has an event type associated with it.
                Each event type must have a unique name within each Smart Contract and can have
                optional Scheduler tags. Each Smart Contract must include a list of all
                [SmartContractEventType](#classes-SmartContractEventType)s included in its
                [activation_hook](../../smart_contracts_api_reference4XX/hooks/#activation_hook) and
                [conversion_hook](../../smart_contracts_api_reference4XX/hooks/#conversion_hook).
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SmartContractEventType",
                args=cls._public_attributes(language_code),
            ),
        )


class SupervisorContractEventType(EventType):
    def __init__(
        self,
        *,
        name: str,
        scheduler_tag_ids: Optional[List[str]] = None,
        overrides_event_types: Optional[List[Tuple[str, str]]] = None,
    ):
        self.overrides_event_types = overrides_event_types
        super().__init__(name=name, scheduler_tag_ids=scheduler_tag_ids)

    def _validate_attributes(self):
        super()._validate_attributes()

        if self.overrides_event_types:
            iterator = types_utils.get_iterator(
                self.overrides_event_types, "Tuple[str, str]", "overrides_event_types"
            )
            for item in iterator:
                types_utils.validate_type(item, tuple, hint="Tuple[str, str]")

    def __repr__(self) -> str:
        return "SupervisorContractEventType"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SupervisorContractEventType",
            docstring="""
                Each scheduled event in a Smart Contract has an event type associated with it.
                Each event type must have a unique name within each Smart Contract and can have
                optional Scheduler tags. Each Smart Contract must include a list of all
                [SupervisorContractEventType](#classes-SupervisorContractEventType)s included in its
                [activation_hook](../../supervisor_contracts_api_reference4XX/hooks/#activation_hook) and
                [conversion_hook](../../supervisor_contracts_api_reference4XX/hooks/#conversion_hook).
            """,  # noqa: E501
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SupervisorContractEventType",
                args=cls._public_attributes(language_code),
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        public_attributes = EventType._public_attributes(language_code)  # noqa: SLF001
        public_attributes.append(
            types_utils.ValueSpec(
                name="overrides_event_types",
                type="Optional[List[Tuple[str, str]]]",
                docstring="""
                    A list of (Smart Contract `alias`, `event_type`) tuples specifying which are
                    the overridden Schedules for each
                    [SupervisorContractEventType](#classes-SupervisorContractEventType). If not
                    provided, this
                    [SupervisorContractEventType](#classes-SupervisorContractEventType) does not
                    override any of the Supervisee Schedules. The Smart Contract alias is the alias
                    defined in the [SmartContractDescriptor](#classes-SmartContractDescriptor).
                    Note that each SupervisorContractEventType can only override one Schedule
                    per Supervisee. If multiple Supervisee Schedules need to be overridden,
                    this has to be done using multiple Supervisee EventTypes.
                """,
            ),
        )
        return public_attributes
