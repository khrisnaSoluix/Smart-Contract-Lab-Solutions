from functools import lru_cache

from .....utils import symbols, types_utils


class ScheduledJob:
    def __init__(self, *, pause_datetime=None, _from_proto=False):
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "pause_datetime": pause_datetime,
                },
            )

        self.pause_datetime = pause_datetime

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="pause_datetime",
                type="Optional[datetime]",
                docstring=(
                    "The `test_pause_at_timestamp` attribute value set in [AccountScheduleTag]("
                    "/api/core_api/#Account_schedule_tags-AccountScheduleTag) to pause the "
                    "account scheduled events. If multiple tags are set with different values for "
                    "`test_pause_at_timestamp`, the earliest timestamp is used. "
                    "Defaults to None, if the attribute is not set or the account "
                    "[EventType](#classes-EventType) has no `scheduler_tag_ids` applied."
                ),
            ),
        ]

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ScheduledJob",
            docstring=(
                "The details associated with a scheduled job for a particular account "
                "[EventType](#classes-EventType)"
                "**Only available in version 3.10.0+**."
            ),
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring=("Constructs a new ScheduledJob."),
                args=cls._public_attributes(language_code),
            ),
        )

    def __eq__(self, other):
        return self.__dict__ == other.__dict__
