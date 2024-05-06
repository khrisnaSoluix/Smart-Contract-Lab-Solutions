from functools import lru_cache

from .....utils import symbols
from .....utils import types_utils
from .....utils.exceptions import InvalidSmartContractError


class UpdateAccountEventTypeDirective:
    def __init__(
        self, *, account_id, event_type, schedule=None, end_datetime=None, _from_proto=False
    ):
        if not end_datetime and not schedule:
            raise InvalidSmartContractError(
                "UpdateAccountEventTypeDirective object has to have either an end_datetime or a "
                "schedule defined"
            )

        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "account_id": account_id,
                    "event_type": event_type,
                    "schedule": schedule,
                    "end_datetime": end_datetime,
                },
            )

        self.account_id = account_id
        self.event_type = event_type
        self.schedule = schedule
        self.end_datetime = end_datetime

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return types_utils.ClassSpec(
            name="UpdateAccountEventTypeDirective",
            docstring="",
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring=(
                    "A [HookDirective](#classes-HookDirectives) that instructs "
                    "updating an Account Event Type. "
                    "**Only available in version 3.8.0+**"
                ),
                args=cls._public_attributes(language_code),
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return [
            types_utils.ValueSpec(
                name="account_id",
                type="str",
                docstring="The Account ID of the `event_type` that will be modified.",
            ),
            types_utils.ValueSpec(
                name="event_type", type="str", docstring="The `event_type` that is to be modified."
            ),
            types_utils.ValueSpec(
                name="schedule",
                type="Optional[EventTypeSchedule]",
                docstring="Optional [EventTypeSchedule](#classes-EventTypeSchedule).",
            ),
            types_utils.ValueSpec(
                name="end_datetime",
                type="Optional[datetime]",
                docstring=(
                    "Optional datetime that indicates when the schedule should stop executing. "
                    "Must be based on the `events_timezone` field defined in the "
                    "[Smart](../../smart_contracts_api_reference3XX/metadata/#events_timezone) and "
                    "[Supervisor](../../supervisor_contracts_api_reference3XX/metadata/#events_timezone) Contract metadata. Note that once "
                    "the end_datetime has been reached, the schedule can **no longer** be updated "
                    "or re-enabled."
                ),
            ),
        ]
