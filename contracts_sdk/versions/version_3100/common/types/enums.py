from .....utils.symbols import DefinedDateTime, ScheduleFailover
from .....utils import types_utils


DefinedDateTime = types_utils.transform_const_enum(
    name="DefinedDateTime",
    const_enum=DefinedDateTime,
    docstring="A datetime that is defined within Vault.",
    hide_keys=("EFFECTIVE_DATETIME"),
)

ScheduleFailover = types_utils.transform_const_enum(
    name="ScheduleFailover",
    const_enum=ScheduleFailover,
    docstring="Specify the failover strategy for this schedule.",
)
