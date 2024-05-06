from ...version_370.smart_contracts.types import *  # noqa: F401, F403
from ..common.types import EventTypeSchedule, HookDirectives, UpdateAccountEventTypeDirective
from ...version_370.smart_contracts import types as types370


def types_registry():
    TYPES = types370.types_registry()

    TYPES["EventTypeSchedule"] = EventTypeSchedule
    TYPES["UpdateAccountEventTypeDirective"] = UpdateAccountEventTypeDirective
    TYPES["HookDirectives"] = HookDirectives

    return TYPES
