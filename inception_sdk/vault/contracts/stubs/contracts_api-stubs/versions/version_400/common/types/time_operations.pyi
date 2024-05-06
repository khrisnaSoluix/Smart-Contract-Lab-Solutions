from .enums import DefinedDateTime as DefinedDateTime
from typing import Any, Optional, Union

class Override:
    year: Optional[int]
    month: Optional[int]
    day: Optional[int]
    hour: Optional[int]
    minute: Optional[int]
    second: Optional[int]

    def __init__(self, *, year: Optional[int]=..., month: Optional[int]=..., day: Optional[int]=..., hour: Optional[int]=..., minute: Optional[int]=..., second: Optional[int]=...) -> None:
        ...

class Shift:
    years: Optional[int]
    months: Optional[int]
    days: Optional[int]
    hours: Optional[int]
    minutes: Optional[int]
    seconds: Optional[int]

    def __init__(self, *, years: Optional[int]=..., months: Optional[int]=..., days: Optional[int]=..., hours: Optional[int]=..., minutes: Optional[int]=..., seconds: Optional[int]=...) -> None:
        ...

class Next:
    month: Optional[int]
    day: int
    hour: Optional[int]
    minute: Optional[int]
    second: Optional[int]

    def __init__(self, *, month: Optional[int]=..., day: int=..., hour: Optional[int]=..., minute: Optional[int]=..., second: Optional[int]=...) -> None:
        ...

class Previous:
    month: Optional[int]
    day: int
    hour: Optional[int]
    minute: Optional[int]
    second: Optional[int]

    def __init__(self, *, month: Optional[int]=..., day: int=..., hour: Optional[int]=..., minute: Optional[int]=..., second: Optional[int]=...) -> None:
        ...

class RelativeDateTime:
    shift: Optional[Shift]
    find: Optional[Union[Next, Previous, Override]]
    origin: DefinedDateTime

    def __init__(self, *, shift: Optional[Shift]=..., find: Optional[Union[Next, Previous, Override]]=..., origin: DefinedDateTime=...) -> None:
        ...