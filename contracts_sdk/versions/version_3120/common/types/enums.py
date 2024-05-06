from .....utils.symbols import SupervisionExecutionMode
from .....utils import types_utils


SupervisionExecutionMode = types_utils.transform_const_enum(
    name="SupervisionExecutionMode",
    const_enum=SupervisionExecutionMode,
    docstring="Determines the execution of a supervisee's hook when triggered with an incoming "
    "request.\n"
    "If INVOKED, the supervised account triggered by the incoming request will be executed "
    "first, and the results provided to the supervisor.\n"
    "If OVERRIDE, the supervisor hook will be executed instead of the supervisee's hook.\n"
    "**Only available in version 3.12+**",
)
