from ...version_380.supervisor_contracts.types import *  # noqa: F401, F403
from ...version_380.supervisor_contracts import types as types380


def types_registry():
    TYPES = types380.types_registry()
    return TYPES
