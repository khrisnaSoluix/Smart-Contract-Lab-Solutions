from functools import lru_cache
from typing import Optional

from .enums import RejectionReason
from .....utils import symbols, types_utils
from .....utils.exceptions import InvalidSmartContractError


class Rejection:
    def __init__(
        self,
        *,
        message: str,
        reason_code: Optional[RejectionReason] = None,  # type: ignore[valid-type]
        _from_proto: Optional[bool] = False,
    ):
        self.message = message
        self.reason_code = reason_code
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        if not self.message:
            raise InvalidSmartContractError("Rejection 'message' must be populated")

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="Rejection",
            docstring="""
            A class that can be returned through some hook result classes to reject a hook run.
            For example, this can be returned to prevent a posting from being committed or to
            reject a parameter update. When a hook rejection is returned, no other directives or
            data can be returned from the hook.
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new `Rejection` object.",
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
                name="message",
                type="str",
                docstring="The message of the rejection.",
            ),
            types_utils.ValueSpec(
                name="reason_code",
                type="Optional[RejectionReason]",
                docstring="""
                The optional reason code for the rejection; defaults to UNKNOWN_REASON."
                """,
            ),
        ]
