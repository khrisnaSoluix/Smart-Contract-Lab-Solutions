# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from dataclasses import dataclass


@dataclass
class CreateCalendarEvent:
    """
    This class represents a Create Calendar event that can be consumed by the Simulation
    endpoint to instruct the creation of a new calendar event.
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param id: id of the Calendar Event
        param calendar_id: id of the calendar the event will be associated with
        param start_timestamp: isoformat string datetime of when the event starts
        param end_timestamp: isoformat string datetime of when the event ends.
    """

    id: str
    calendar_id: str
    start_timestamp: str
    end_timestamp: str

    def to_dict(self):
        return {"create_calendar_event": self.__dict__}


@dataclass
class CreateCalendar:
    """
    This class represents creation of calendar definition that can be consumed by the Simulation
    endpoint to instruct the creation of a new calendar.
    Please note that `.to_dict()` must be called when the object is passed into vault_caller.

    Args:
        param id: id of the Calendar to be created
    """

    id: str

    def to_dict(self):
        return {"create_calendar": self.__dict__}
