from functools import lru_cache

from .....utils import symbols
from .....utils import types_utils


class ScheduleSkip:
    def __init__(self, *, end, _from_proto=False):
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "end": end,
                },
            )
        self.end = end

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return types_utils.ClassSpec(
            name="ScheduleSkip",
            docstring="""
                Defines the skip period for a Schedule. **Only available in version 3.11.0+**
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="",
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
                name="end",
                type="datetime",
                docstring="The local date/time when the Schedule will be skipped until.",
            )
        ]
