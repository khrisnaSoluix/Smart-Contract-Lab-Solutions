from functools import lru_cache
import bisect

from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Tuple, Any, Union
from .....utils import exceptions, symbols, types_utils
from .....utils.timezone_utils import validate_timezone_is_utc
from ..types import Balance, OptionalValue, UnionItemValue


_timeseries_value_type_str = (
    "Union[Balance, bool, Decimal, str, datetime, OptionalValue, UnionItemValue, int]"
)
_parameter_value_type_str = "Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]"


class TimeseriesItem:
    at_datetime: datetime
    value: Union[Balance, bool, Decimal, str, datetime, OptionalValue, UnionItemValue, int]

    def __init__(self, item, _from_proto=False):
        if not _from_proto:
            validate_timezone_is_utc(
                item[0],
                "at_datetime",
                "TimeseriesItem",
            )
        self.at_datetime = item[0]
        self.value = item[1]

    def __repr__(self):
        return f"({self.at_datetime}, {self.value})"

    def __eq__(self, other):
        return (
            self.__class__ == other.__class__
            and self.at_datetime == other.at_datetime
            and self.value == other.value
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return types_utils.ClassSpec(
            name="TimeseriesItem",
            docstring="""
                Represents a timeseries datapoint, containing a datetime and value.
            """,
            public_attributes=cls._public_attributes(language_code),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="at_datetime",
                type="datetime",
                docstring=(
                    "The datetime of the timeseries datapoint. "
                    "Must be a timezone-aware UTC datetime using the ZoneInfo class."
                ),
            ),
            types_utils.ValueSpec(
                name="value",
                type=_timeseries_value_type_str,
                docstring=(
                    "The value of the timeseries datapoint at 'at_datetime'. "
                    "The type of this value will depend type of the timeseries "
                    "(`BalanceTimeseries`, `FlagTimeseries`, `ParameterTimeseries`)."
                ),
            ),
        ]


class Timeseries(list):

    return_on_empty = None

    def __init__(
        self,
        iterable: Optional[List[Tuple[datetime, Any]]] = None,
        _from_proto: Optional[bool] = False,
    ) -> None:
        self._from_proto = _from_proto
        if iterable is None:
            iterable = []
        self.extend(TimeseriesItem(item, _from_proto) for item in iterable)

    def at(
        self, *, at_datetime: datetime, inclusive: bool = True
    ) -> Union[Balance, bool, Decimal, str, datetime, OptionalValue, UnionItemValue, int]:
        validate_timezone_is_utc(
            at_datetime,
            "at_datetime",
            f"{self.__repr__()}.at()",
        )
        start_datetimes = [entry.at_datetime for entry in self]
        if inclusive:
            # bisect_right gives the index of the first entry strictly exceeding the datetime
            index = bisect.bisect_right(start_datetimes, at_datetime) - 1
        else:
            # bisect_left gives the index of the first entry exceeding or equal to the datetime
            index = bisect.bisect_left(start_datetimes, at_datetime) - 1
        if index >= 0:
            return self[index].value
        if self.return_on_empty is not None:
            return self.return_on_empty()  # type: ignore
        raise exceptions.InvalidSmartContractError("No values provided as of date %s" % at_datetime)

    def before(
        self, *, at_datetime: datetime
    ) -> Union[Balance, bool, Decimal, str, datetime, OptionalValue, UnionItemValue, int]:
        validate_timezone_is_utc(
            at_datetime,
            "at_datetime",
            f"{self.__repr__()}.before()",
        )
        return self.at(at_datetime=at_datetime, inclusive=False)

    def latest(
        self,
    ) -> Union[Balance, bool, Decimal, str, datetime, OptionalValue, UnionItemValue, int]:
        if not self:
            if self.return_on_empty is not None:
                return self.return_on_empty()  # type: ignore
            raise exceptions.InvalidSmartContractError("No values provided")
        return self[-1].value

    def all(self) -> List[TimeseriesItem]:
        return self

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="Timeseries",
            docstring="A generic timeseries.",
            public_attributes=[],
            public_methods=[
                types_utils.MethodSpec(
                    name="at",
                    docstring=(
                        "Returns the latest available TimeseriesItem as of the given timestamp."
                    ),
                    args=[
                        types_utils.ValueSpec(
                            name="datetime",
                            type="datetime",
                            docstring=(
                                "The timestamp as of which to fetch the latest TimeseriesItem. "
                                "Must be a timezone-aware UTC datetime using the ZoneInfo class."
                            ),
                        ),
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type="TimeseriesItem",
                        docstring="The latest TimeseriesItem as of the timestamp provided.",
                    ),
                ),
                types_utils.MethodSpec(
                    name="before",
                    docstring=(
                        "Returns the latest available TimeseriesItem as of just before the "
                        "given timestamp."
                    ),
                    args=[
                        types_utils.ValueSpec(
                            name="at_datetime",
                            type="datetime",
                            docstring=(
                                "The timestamp just before which to fetch the "
                                "latest TimeseriesItem. "
                                "Must be a timezone-aware UTC datetime using the ZoneInfo class."
                            ),
                        ),
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type=cls.item_type,
                        docstring=(
                            "The latest TimeseriesItem as of just before the timestamp provided."
                        ),
                    ),
                ),
                types_utils.MethodSpec(
                    name="latest",
                    docstring="Returns the latest available TimeseriesItem.",
                    args=[],
                    return_value=types_utils.ValueSpec(
                        name=None,
                        type="TimeseriesItem",
                        docstring="The latest available TimeseriesItem.",
                    ),
                ),
                types_utils.MethodSpec(
                    name="all",
                    docstring=(
                        "Returns a list of all available TimeseriesItem values across time."
                    ),
                    args=[],
                    return_value=types_utils.ValueSpec(
                        name=None,
                        type="List[TimeseriesItem]",
                        docstring="All available TimeseriesItem values and their timestamps.",
                    ),
                ),
            ],
        )

    def __repr__(self):
        return "Timeseries"


class BalanceTimeseries(Timeseries):
    return_on_empty = lambda *_: Balance()  # type: ignore

    def __init__(
        self,
        iterable: Optional[List[Tuple[datetime, Balance]]] = None,
        _from_proto: Optional[bool] = False,
    ) -> None:
        super().__init__(iterable, _from_proto)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="BalanceTimeseries",
            docstring="""
                A time series of balances for the Account.

                The 'at', 'before', and 'latest' methods (and the `.value` attribute of each
                [TimeseriesItem](#classes-TimeseriesItem) returned via 'all') return a Balance
                object.

                To find the "total" balance for the Account, or a given address inside the
                Account, you must sum the relevant Balance objects for the appropriate datetime.
                """,
            public_attributes=[],
            public_methods=[
                types_utils.MethodSpec(
                    name="at",
                    docstring=(
                        "Returns the latest available Balance object as of the given datetime."
                    ),
                    args=[
                        types_utils.ValueSpec(
                            name="at_datetime",
                            type="datetime",
                            docstring=(
                                "The datetime from which to fetch the latest Balance object. "
                                "Must be a timezone-aware UTC datetime using the ZoneInfo class."
                            ),
                        ),
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type="Balance",
                        docstring=("The latest Balance object as of the datetime provided."),
                    ),
                ),
                types_utils.MethodSpec(
                    name="before",
                    docstring=(
                        "Returns the latest available Balance object as of just before the "
                        "given datetime."
                    ),
                    args=[
                        types_utils.ValueSpec(
                            name="at_datetime",
                            type="datetime",
                            docstring=(
                                "The datetime just before which to fetch the "
                                "latest Balance object. "
                                "Must be a timezone-aware UTC datetime using the ZoneInfo class."
                            ),
                        ),
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type="Balance",
                        docstring=(
                            "The latest Balance object as of just before the datetime provided."
                        ),
                    ),
                ),
                types_utils.MethodSpec(
                    name="latest",
                    docstring="Returns the latest available Balance object.",
                    args=[],
                    return_value=types_utils.ValueSpec(
                        name=None,
                        type="Balance",
                        docstring="The latest available Balance object.",
                    ),
                ),
                types_utils.MethodSpec(
                    name="all",
                    docstring=(
                        "Returns a list of all available Balance object values across time."
                    ),
                    args=[],
                    return_value=types_utils.ValueSpec(
                        name=None,
                        type="List[TimeseriesItem]",
                        docstring="All available Balance object values and their datetimes.",
                    ),
                ),
            ],
        )

    def __repr__(self):
        return "BalanceTimeseries"


class FlagTimeseries(Timeseries):

    return_on_empty = lambda *_: False  # type:ignore

    def __init__(self, iterable: Optional[List[Tuple[datetime, bool]]] = None) -> None:
        super().__init__(iterable)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="FlagTimeseries",
            docstring="""
                    A timeseries for the active status for a given flag definition.
                    If the flag definition does not exist the timeseries will be empty
                    and .at() will always return False.
                """,
            public_attributes=[],
            public_methods=[
                types_utils.MethodSpec(
                    name="at",
                    docstring=("Returns the latest available flag as of the given datetime."),
                    args=[
                        types_utils.ValueSpec(
                            name="at_datetime",
                            type="datetime",
                            docstring=(
                                "The datetime from which to fetch the latest flag. "
                                "Must be a timezone-aware UTC datetime using the ZoneInfo class."
                            ),
                        ),
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type="bool",
                        docstring=("The latest flag as of the datetime provided."),
                    ),
                ),
                types_utils.MethodSpec(
                    name="before",
                    docstring=(
                        "Returns the latest available flag as of just before the " "given datetime."
                    ),
                    args=[
                        types_utils.ValueSpec(
                            name="at_datetime",
                            type="datetime",
                            docstring=(
                                "The datetime just before which to fetch the latest flag. "
                                "Must be a timezone-aware UTC datetime using the ZoneInfo class."
                            ),
                        ),
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type="bool",
                        docstring=("The latest flag as of just before the datetime provided."),
                    ),
                ),
                types_utils.MethodSpec(
                    name="latest",
                    docstring="Returns the latest available flag.",
                    args=[],
                    return_value=types_utils.ValueSpec(
                        name=None,
                        type="bool",
                        docstring="The latest available flag.",
                    ),
                ),
                types_utils.MethodSpec(
                    name="all",
                    docstring=("Returns a list of all available flag values across time."),
                    args=[],
                    return_value=types_utils.ValueSpec(
                        name=None,
                        type="List[TimeseriesItem]",
                        docstring="All available flag values and their datetimes.",
                    ),
                ),
            ],
        )

    def __repr__(self):
        return "FlagTimeseries"


class ParameterTimeseries(Timeseries):

    return_on_empty = None

    def __init__(
        self,
        iterable: Optional[
            List[Tuple[datetime, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]]]
        ] = None,
    ) -> None:
        super().__init__(iterable)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ParameterTimeseries",
            docstring="""
                    A timeseries of Parameter objects.
                """,
            public_attributes=[],
            public_methods=[
                types_utils.MethodSpec(
                    name="at",
                    docstring=(
                        "Returns the latest available parameter value as of the given datetime."
                    ),
                    args=[
                        types_utils.ValueSpec(
                            name="at_datetime",
                            type="datetime",
                            docstring=(
                                "The datetime as of which to fetch the latest parameter value. "
                                "Must be a timezone-aware UTC datetime using the ZoneInfo class."
                            ),
                        ),
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type=_parameter_value_type_str,
                        docstring=("The latest parameter value as of the datetime provided."),
                    ),
                ),
                types_utils.MethodSpec(
                    name="before",
                    docstring=(
                        "Returns the latest available parameter value as of just before the "
                        "given datetime."
                    ),
                    args=[
                        types_utils.ValueSpec(
                            name="at_datetime",
                            type="datetime",
                            docstring=(
                                "The datetime just before which to fetch the "
                                "latest parameter value. "
                                "Must be a timezone-aware UTC datetime using the ZoneInfo class."
                            ),
                        ),
                    ],
                    return_value=types_utils.ReturnValueSpec(
                        type=_parameter_value_type_str,
                        docstring=(
                            "The latest parameter value as of just before the datetime provided."
                        ),
                    ),
                ),
                types_utils.MethodSpec(
                    name="latest",
                    docstring="Returns the latest available parameter value.",
                    args=[],
                    return_value=types_utils.ValueSpec(
                        name=None,
                        type=_parameter_value_type_str,
                        docstring="The latest available parameter value.",
                    ),
                ),
                types_utils.MethodSpec(
                    name="all",
                    docstring=(
                        "Returns a list of all available parameter value values across time."
                    ),
                    args=[],
                    return_value=types_utils.ValueSpec(
                        name=None,
                        type="List[TimeseriesItem]",
                        docstring="All available parameter value values and their datetimes.",
                    ),
                ),
            ],
        )

    def __repr__(self):
        return "ParameterTimeseries"
