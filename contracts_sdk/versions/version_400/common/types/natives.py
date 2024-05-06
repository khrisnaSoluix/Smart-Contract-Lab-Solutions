import calendar
import collections
import datetime
import decimal
import json
import math
import typing
import zoneinfo

# Ignore lint checks to enable more generic compatibility of third party module imports
from dateutil import parser, relativedelta  # type: ignore
from .....utils import types_utils


anyObject = types_utils.NativeObjectSpec(
    name="Any",
    object=typing.Any,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.Any",
)

calendarIsleapFunction = types_utils.NativeObjectSpec(
    name="isleap",
    object=calendar.isleap,
    package=calendar,
    docs="https://docs.python.org/3/library/calendar.html#calendar.isleap",
)

calendarMonthrangeFunction = types_utils.NativeObjectSpec(
    name="monthrange",
    object=calendar.monthrange,
    package=calendar,
    docs="https://docs.python.org/3/library/calendar.html#calendar.monthrange",
)

callableObject = types_utils.NativeObjectSpec(
    name="Callable",
    object=typing.Callable,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.Callable",
)

datetimeObject = types_utils.NativeObjectSpec(
    name="datetime",
    object=datetime.datetime,
    package=datetime,
    description=(
        "Note: `datetime` module `today`, `timetuple` and `strftime` methods are not available."
    ),
)

decimalObject = types_utils.NativeObjectSpec(
    name="Decimal", object=decimal.Decimal, package=decimal
)

defaultDict = types_utils.NativeObjectSpec(
    name="defaultdict", object=collections.defaultdict, package=collections
)

defaultDictObject = types_utils.NativeObjectSpec(
    name="DefaultDict",
    object=typing.DefaultDict,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.DefaultDict",
)

dictObject = types_utils.NativeObjectSpec(
    name="Dict",
    object=typing.Dict,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.Dict",
)

iterableObject = types_utils.NativeObjectSpec(
    name="Iterable",
    object=typing.Iterable,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.Iterable",
)

iteratorObject = types_utils.NativeObjectSpec(
    name="Iterator",
    object=typing.Iterator,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.Iterator",
)

jsonDumpsObject = types_utils.NativeObjectSpec(name="dumps", object=json.dumps, package=json)

jsonLoadsObject = types_utils.NativeObjectSpec(name="loads", object=json.loads, package=json)

listObject = types_utils.NativeObjectSpec(
    name="List",
    object=typing.List,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.List",
)

mappingObject = types_utils.NativeObjectSpec(
    name="Mapping",
    object=typing.Mapping,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.Mapping",
)

mathObject = types_utils.NativeObjectSpec(name="math", object=math, package=math)

namedTupleObject = types_utils.NativeObjectSpec(
    name="NamedTuple",
    object=typing.NamedTuple,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.NamedTuple",
)

newTypeObject = types_utils.NativeObjectSpec(
    name="NewType",
    object=typing.NewType,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.NewType",
)

noReturnObject = types_utils.NativeObjectSpec(
    name="NoReturn",
    object=typing.NoReturn,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.NoReturn",
)

optionalObject = types_utils.NativeObjectSpec(
    name="Optional",
    object=typing.Optional,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.Optional",
)

parseToDatetimeObject = types_utils.NativeObjectSpec(
    name="parse",
    object=parser.parse,
    package=parser,
    docs="https://dateutil.readthedocs.io/en/stable/parser.html#dateutil.parser.parse",
)

relativedeltaObject = types_utils.NativeObjectSpec(
    name="relativedelta",
    object=relativedelta.relativedelta,
    package=relativedelta,
    docs="https://dateutil.readthedocs.io/en/stable/relativedelta.html",
)

roundFloorObject = types_utils.NativeObjectSpec(
    name="ROUND_FLOOR", object=decimal.ROUND_FLOOR, package=decimal
)

roundHalfDownObject = types_utils.NativeObjectSpec(
    name="ROUND_HALF_DOWN", object=decimal.ROUND_HALF_DOWN, package=decimal
)

roundHalfUpObject = types_utils.NativeObjectSpec(
    name="ROUND_HALF_UP", object=decimal.ROUND_HALF_UP, package=decimal
)

roundCeilingObject = types_utils.NativeObjectSpec(
    name="ROUND_CEILING",
    object=decimal.ROUND_CEILING,
    package=decimal,
)

roundDownObject = types_utils.NativeObjectSpec(
    name="ROUND_DOWN",
    object=decimal.ROUND_DOWN,
    package=decimal,
)

roundHalfEvenObject = types_utils.NativeObjectSpec(
    name="ROUND_HALF_EVEN",
    object=decimal.ROUND_HALF_EVEN,
    package=decimal,
)

round05UpObject = types_utils.NativeObjectSpec(
    name="ROUND_05UP",
    object=decimal.ROUND_05UP,
    package=decimal,
)

setObject = types_utils.NativeObjectSpec(
    name="Set",
    object=typing.Set,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.Set",
)

tupleObject = types_utils.NativeObjectSpec(
    name="Tuple",
    object=typing.Tuple,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.Tuple",
)

typeObject = types_utils.NativeObjectSpec(
    name="Type",
    object=typing.Type,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.Type",
)

unionObject = types_utils.NativeObjectSpec(
    name="Union",
    object=typing.Union,
    package=typing,
    docs="https://docs.python.org/3/library/typing.html#typing.Union",
)

zoneInfoObject = types_utils.NativeObjectSpec(
    name="ZoneInfo",
    object=zoneinfo.ZoneInfo,
    package=zoneinfo,
    docs="https://docs.python.org/3/library/zoneinfo.html",
)

# This is a map of packages to methods that are available to be imported. It is used to validate
# imports in sandbox utils.
# If a package has an import of "all_required" it means that the whole package needs to be imported
# e.g. `from math import pow` is not allowed.
ALLOWED_NATIVES = {
    "calendar": {
        "isleap": calendarIsleapFunction,
        "monthrange": calendarMonthrangeFunction,
    },
    "collections": {"defaultdict": defaultDict},
    "datetime": {"datetime": datetimeObject},
    "dateutil.parser": {"parse": parseToDatetimeObject},
    "dateutil.relativedelta": {"relativedelta": relativedeltaObject},
    "decimal": {
        "Decimal": decimalObject,
        "ROUND_05UP": round05UpObject,
        "ROUND_CEILING": roundCeilingObject,
        "ROUND_DOWN": roundDownObject,
        "ROUND_FLOOR": roundFloorObject,
        "ROUND_HALF_DOWN": roundHalfDownObject,
        "ROUND_HALF_EVEN": roundHalfEvenObject,
        "ROUND_HALF_UP": roundHalfUpObject,
    },
    "json": {"dumps": jsonDumpsObject, "loads": jsonLoadsObject},
    "math": {"all_required": mathObject},
    "typing": {
        "Any": anyObject,
        "Callable": callableObject,
        "DefaultDict": defaultDictObject,
        "Dict": dictObject,
        "Iterable": iterableObject,
        "Iterator": iteratorObject,
        "List": listObject,
        "Mapping": mappingObject,
        "NamedTuple": namedTupleObject,
        "NewType": newTypeObject,
        "NoReturn": noReturnObject,
        "Optional": optionalObject,
        "Set": setObject,
        "Type": typeObject,
        "Tuple": tupleObject,
        "Union": unionObject,
    },
    "zoneinfo": {"ZoneInfo": zoneInfoObject},
}
