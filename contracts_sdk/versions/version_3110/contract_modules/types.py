from ...version_3100.contract_modules.types import *  # noqa: F401, F403
from ...version_3100.contract_modules import types as types3100
from ..common.types import (
    HookDirectives,
    ScheduleSkip,
    UpdateAccountEventTypeDirective,
)


def types_registry():
    TYPES = types3100.types_registry()
    TYPES["HookDirectives"] = HookDirectives
    TYPES["ScheduleSkip"] = ScheduleSkip
    TYPES["UpdateAccountEventTypeDirective"] = UpdateAccountEventTypeDirective

    return TYPES
