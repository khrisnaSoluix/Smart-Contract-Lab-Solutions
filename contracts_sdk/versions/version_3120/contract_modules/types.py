from ...version_3110.contract_modules.types import *  # noqa: F401, F403
from ...version_3110.contract_modules import types as types3110
from ..common.types import (
    SupervisedHooks,
    SupervisionExecutionMode,
    HookDirectives,
    InstructAccountNotificationDirective,
)
from ....utils.feature_flags import (
    is_fflag_enabled,
    PRE_POSTING_SUPERVISION,
    CONTRACTS_NOTIFICATION_EVENT,
)


def types_registry():
    TYPES = types3110.types_registry()
    if is_fflag_enabled(feature_flag=PRE_POSTING_SUPERVISION):
        TYPES["SupervisedHooks"] = SupervisedHooks
        TYPES["SupervisionExecutionMode"] = SupervisionExecutionMode
    if is_fflag_enabled(feature_flag=CONTRACTS_NOTIFICATION_EVENT):
        TYPES["InstructAccountNotificationDirective"] = InstructAccountNotificationDirective
        TYPES["HookDirectives"] = HookDirectives
    return TYPES
