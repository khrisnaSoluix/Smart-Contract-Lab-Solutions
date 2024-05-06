from ...version_3100.supervisor_contracts.types import *  # noqa: F401, F403
from ...version_3100.supervisor_contracts import types as types3100
from ....utils.exceptions import InvalidSmartContractError
from ....utils import symbols, types_utils
from ..common.types import (
    HookDirectives,
    ScheduleSkip,
    UpdateAccountEventTypeDirective,
)
from functools import lru_cache

class UpdatePlanEventTypeDirective(types3100.UpdatePlanEventTypeDirective):
    def __init__(
        self,
        *,
        plan_id,
        event_type,
        schedule=None,
        schedule_method=None,
        end_datetime=None,
        skip=None,
        _from_proto=False
    ):
        _validate_missing_params = skip is None
        if not _from_proto:
            if skip is None:
                if not schedule and not schedule_method and not end_datetime:
                    raise InvalidSmartContractError(
                        "UpdatePlanEventTypeDirective object has to have either an end_datetime, a "
                        "schedule, schedule_method, or skip defined"
                    )
            else:
                self._spec().assert_constructor_args(self._registry, {"skip": skip})
        super().__init__(
            plan_id=plan_id,
            event_type=event_type,
            schedule=schedule,
            schedule_method=schedule_method,
            end_datetime=end_datetime,
            _from_proto=_from_proto,
            _validate_missing_params=_validate_missing_params,
        )
        self.skip = skip

    @classmethod
    @lru_cache()

    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        attributes = super()._public_attributes(language_code=language_code)
        attributes.append(
            types_utils.ValueSpec(
                name="skip",
                type="Optional[Union[bool, ScheduleSkip]]",
                docstring="""
                    An optional flag to skip a schedule indefinitely (True), unskip a
                    Schedule (False), or to skip until a specified time (ScheduleSkip).
                    **Only available in version 3.11.0+**
                """,
            )
        )
        return attributes


def types_registry():
    TYPES = types3100.types_registry()
    TYPES["HookDirectives"] = HookDirectives
    TYPES["ScheduleSkip"] = ScheduleSkip
    TYPES["UpdateAccountEventTypeDirective"] = UpdateAccountEventTypeDirective
    TYPES["UpdatePlanEventTypeDirective"] = UpdatePlanEventTypeDirective

    return TYPES
