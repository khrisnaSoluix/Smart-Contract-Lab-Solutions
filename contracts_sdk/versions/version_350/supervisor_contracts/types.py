from ...version_340.supervisor_contracts.types import *  # noqa: F401, F403
from ...version_340.supervisor_contracts import types as types340


def types_registry():
    TYPES = types340.types_registry()
    return TYPES
