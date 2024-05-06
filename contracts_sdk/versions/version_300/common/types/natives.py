import calendar
import collections
import json
import math
import datetime
from dateutil import parser, relativedelta
import decimal

from .....utils import types_utils


calendarObject = types_utils.NativeObjectSpec(
    name='calendar',
    object=calendar,
    package=calendar,
    description=(
        'Note: `calendar` module `HTMLCalendar.formatyearpage` method is not available.'
    )
)

datetimeObject = types_utils.NativeObjectSpec(
    name='datetime',
    object=datetime.datetime,
    package=datetime,
    description=(
        'Note: `datetime` module `today`, `timetuple` and `strftime` methods are not available.'
    )
)

decimalObject = types_utils.NativeObjectSpec(
    name='Decimal',
    object=decimal.Decimal,
    package=decimal
)

defaultDict = types_utils.NativeObjectSpec(
    name='defaultdict',
    object=collections.defaultdict,
    package=collections
)

mathObject = types_utils.NativeObjectSpec(
    name='math',
    object=math,
    package=math
)

jsonDumpsObject = types_utils.NativeObjectSpec(
    name='json_dumps',
    object=json.dumps,
    package=json
)

jsonLoadsObject = types_utils.NativeObjectSpec(
    name='json_loads',
    object=json.loads,
    package=json
)

timedeltaObject = types_utils.NativeObjectSpec(
    name='timedelta',
    object=relativedelta.relativedelta,
    package=relativedelta,
    docs='https://dateutil.readthedocs.io/en/stable/relativedelta.html'
)

parseToDatetimeObject = types_utils.NativeObjectSpec(
    name='parse_to_datetime',
    object=parser.parse,
    package=parser,
    docs='https://dateutil.readthedocs.io/en/stable/parser.html#dateutil.parser.parse'
)

roundFloorObject = types_utils.NativeObjectSpec(
    name='ROUND_FLOOR',
    object=decimal.ROUND_FLOOR,
    package=decimal
)

roundHalfDownObject = types_utils.NativeObjectSpec(
    name='ROUND_HALF_DOWN',
    object=decimal.ROUND_HALF_DOWN,
    package=decimal
)

roundHalfUpObject = types_utils.NativeObjectSpec(
    name='ROUND_HALF_UP',
    object=decimal.ROUND_HALF_UP,
    package=decimal
)
