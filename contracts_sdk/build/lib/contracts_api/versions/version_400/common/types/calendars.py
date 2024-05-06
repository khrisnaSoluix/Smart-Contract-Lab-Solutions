from datetime import datetime
from functools import lru_cache

from .....utils import symbols, types_utils
from .....utils.timezone_utils import validate_timezone_is_utc

from typing import List, Optional


class CalendarEvent:
    def __init__(
        self,
        *,
        id: str,
        calendar_id: str,
        start_datetime: datetime,
        end_datetime: datetime,
        _from_proto: bool = False
    ):

        self.id = id
        self.calendar_id = calendar_id
        self.start_datetime = start_datetime
        self.end_datetime = end_datetime
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        validate_timezone_is_utc(
            self.start_datetime,
            "start_datetime",
            "CalendarEvent",
        )
        validate_timezone_is_utc(
            self.end_datetime,
            "end_datetime",
            "CalendarEvent",
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="id",
                type="str",
                docstring="""
                    Uniquely identifies the Calendar Event in the Vault Calendar resource.
                """,
            ),
            types_utils.ValueSpec(
                name="calendar_id",
                type="str",
                docstring="""
                    The ID of the Calendar that this Calendar Event belongs to.
                """,
            ),
            types_utils.ValueSpec(
                name="start_datetime",
                type="datetime",
                docstring="""
                    The logical datetime at which the Calendar Event starts taking effect.
                    Must be a timezone-aware UTC datetime using the ZoneInfo class.
                """,
            ),
            types_utils.ValueSpec(
                name="end_datetime",
                type="datetime",
                docstring="""
                    The logical datetime at which the Calendar Event stops taking effect.
                    Must be a timezone-aware UTC datetime using the ZoneInfo class.
                """,
            ),
        ]

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="CalendarEvent",
            docstring="""
                A unique event resource defined in the Vault Calendar.
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),
            ),
        )


class CalendarEvents(list):
    def __init__(self, *, calendar_events: Optional[List[CalendarEvent]] = None):
        calendar_events_default_list = []
        if calendar_events is not None:
            calendar_events_default_list = calendar_events
        super().__init__(calendar_events_default_list)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="CalendarEvents",
            docstring="A list of CalendarEvent objects.",
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=[
                    types_utils.ValueSpec(
                        name="calendar_events",
                        type="Optional[List[CalendarEvent]]",
                        docstring="""
                            A list of CalendarEvent objects.
                        """,
                    ),
                ],
            ),
        )
