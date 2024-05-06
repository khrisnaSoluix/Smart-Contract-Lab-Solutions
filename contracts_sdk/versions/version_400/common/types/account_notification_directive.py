from functools import lru_cache
from typing import Dict

from .....utils.exceptions import (
    InvalidSmartContractError,
)
from .....utils import symbols, types_utils


class AccountNotificationDirective:
    def __init__(
        self,
        *,
        notification_type: str,
        notification_details: Dict[str, str],
        _from_proto: bool = False
    ):
        self.notification_type = notification_type
        self.notification_details = notification_details
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        types_utils.validate_type(self.notification_details, dict)
        if not self.notification_details:
            raise InvalidSmartContractError(
                "AccountNotificationDirective 'notification_details' must be populated"
            )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return types_utils.ClassSpec(
            name="AccountNotificationDirective",
            docstring="",
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="""
                        A Hook Directive that instructs the publication of a notification.
                    """,
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
                name="notification_type",
                type="str",
                docstring="""
                        The `type` of notification.
                        Used to identify how a notification should be processed.
                    """,
            ),
            types_utils.ValueSpec(
                name="notification_details",
                type="Dict[str, str]",
                docstring="""
                        The information (key-value pairs of data)
                        to be published with the notification.
                    """,
            ),
        ]
