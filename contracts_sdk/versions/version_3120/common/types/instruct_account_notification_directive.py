from functools import lru_cache

from .....utils import symbols, types_utils


class InstructAccountNotificationDirective:
    def __init__(self, *, account_id, notification_type, notification_details, _from_proto=False):

        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "account_id": account_id,
                    "notification_type": notification_type,
                    "notification_details": notification_details,
                },
            )

        self.account_id = account_id
        self.notification_type = notification_type
        self.notification_details = notification_details

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return types_utils.ClassSpec(
            name="InstructAccountNotificationDirective",
            docstring="",
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="""
                        A [HookDirective](#classes-HookDirectives) that instructs
                        the publication of a notification.
                        **Only available in version 3.12+**
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
                name="account_id",
                type="str",
                docstring="The Account ID of the account sending the notification.",
            ),
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
