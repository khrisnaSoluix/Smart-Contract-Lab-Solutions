from functools import lru_cache

from ....version_390.common import types as types390
from .....utils import symbols
from .....utils import types_utils
from .....utils.exceptions import InvalidSmartContractError


class UpdateAccountEventTypeDirective(types390.UpdateAccountEventTypeDirective):
    def __init__(
        self,
        *,
        account_id,
        event_type,
        schedule=None,
        schedule_method=None,
        end_datetime=None,
        _from_proto=False,
        _validate_missing_params=True,
    ):
        if not _from_proto:
            if _validate_missing_params:
                if not end_datetime and not schedule and not schedule_method:
                    raise InvalidSmartContractError(
                        "UpdateAccountEventTypeDirective object must have either an "
                        "end_datetime, a schedule or schedule_method defined"
                    )
            if schedule is not None and schedule_method is not None:
                raise InvalidSmartContractError(
                    "UpdateAccountEventTypeDirective cannot contain both"
                    " schedule and schedule_method fields"
                )
            kwargs = {
                "account_id": account_id,
                "event_type": event_type,
                "schedule": schedule,
                "end_datetime": end_datetime,
                "schedule_method": schedule_method,
            }
            self._spec().assert_constructor_args(self._registry, kwargs)

        self.account_id = account_id
        self.event_type = event_type
        self.schedule = schedule
        self.end_datetime = end_datetime
        self.schedule_method = schedule_method

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        attributes = super()._public_attributes(language_code=language_code)
        attributes.append(
            types_utils.ValueSpec(
                name="schedule_method",
                type="Optional[EndOfMonthSchedule]",
                docstring=(
                    "Optional [EndOfMonthSchedule](#classes-EndOfMonthSchedule)."
                    "**Only available in version 3.10.0+**"
                ),
            )
        )
        return attributes
