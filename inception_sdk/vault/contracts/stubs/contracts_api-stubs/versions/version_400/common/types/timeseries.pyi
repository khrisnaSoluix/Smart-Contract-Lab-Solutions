from ..types import Balance as Balance, OptionalValue as OptionalValue, UnionItemValue as UnionItemValue
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional, Tuple, Union

class TimeseriesItem:
    at_datetime: datetime
    # MANUAL-FIX (TM-78625): set to Any as original type just results in type warnings (e.g. 
    # parameter timeseries item cannot be a Balance)
    value: Any

    def __init__(self, item, _from_proto: bool=...) -> None:
        ...

    def __eq__(self, other):
        ...

class Timeseries(list):
    return_on_empty: Any

    def __init__(self, iterable: Optional[List[Tuple[datetime, Any]]]=..., _from_proto: Optional[bool]=...) -> None:
        ...
    # MANUAL-FIX (TM-78625): set to Any as original type just results in type warnings (e.g. 
    # parameter timeseries item cannot be a Balance)
    def at(self, at_datetime: datetime, *, inclusive: bool=...) -> Any:
        ...
    # MANUAL-FIX (TM-78625): set to Any as original type just results in type warnings (e.g. 
    # parameter timeseries item cannot be a Balance)
    def before(self, at_datetime: datetime) -> Any:
        ...
    # MANUAL-FIX (TM-78625): set to Any as original type just results in type warnings (e.g. 
    # parameter timeseries item cannot be a Balance)
    def latest(self) -> Any:
        ...
    # MANUAL-FIX (TM-78625): set to Any as original type just results in type warnings (e.g. 
    # parameter timeseries item cannot be a Balance)
    def all(self) -> List[TimeseriesItem]:
        ...

class BalanceTimeseries(Timeseries):
    return_on_empty: Any

    def __init__(self, iterable: Optional[List[Tuple[datetime, Balance]]]=..., _from_proto: Optional[bool]=...) -> None:
        ...

class FlagTimeseries(Timeseries):
    return_on_empty: Any

    def __init__(self, iterable: Optional[List[Tuple[datetime, bool]]]=...) -> None:
        ...

class ParameterTimeseries(Timeseries):
    return_on_empty: Any

    def __init__(self, iterable: Optional[List[Tuple[datetime, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]]]]=...) -> None:
        ...