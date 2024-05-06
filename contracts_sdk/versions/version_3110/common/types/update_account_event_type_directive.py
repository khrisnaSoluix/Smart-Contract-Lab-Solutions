from ....version_3100.common import types as types3100
from .....utils import symbols
from .....utils import types_utils
from .....utils.exceptions import InvalidSmartContractError
from functools import lru_cache


class UpdateAccountEventTypeDirective(types3100.UpdateAccountEventTypeDirective):
    def __init__(
        self,
        *,
        account_id,
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
                if not end_datetime and not schedule and not schedule_method:
                    raise InvalidSmartContractError(
                        "UpdateAccountEventTypeDirective object must have either an "
                        "end_datetime, a schedule, schedule_method, or skip defined"
                    )
            else:
                self._spec().assert_constructor_args(self._registry, {"skip": skip})
        super().__init__(
            account_id=account_id,
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
