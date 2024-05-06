from functools import lru_cache

from .....utils import symbols
from .....utils import types_utils


class AmendScheduleDirective:
    def __init__(self, *, event_type, new_schedule, request_id, account_id, _from_proto=False):
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {
                    "event_type": event_type,
                    "new_schedule": new_schedule,
                    "request_id": request_id,
                    "account_id": account_id,
                },
            )

        self.event_type = event_type
        self.new_schedule = new_schedule
        self.request_id = request_id
        self.account_id = account_id

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return types_utils.ClassSpec(
            name="AmendScheduleDirective",
            docstring="""
                A [HookDirective](#classes-HookDirectives) that instructs amending a Schedule.
                **Only available in version 3.4.0+**.
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new AmendScheduleDirective",
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
                name="event_type",
                type="str",
                docstring="The event_type to change the schedule for.",
            ),
            types_utils.ValueSpec(
                name="new_schedule", type="Dict[str, str]", docstring="The new schedule."
            ),
            types_utils.ValueSpec(
                name="request_id",
                type="str",
                docstring="""
                    The idempotency key. The hook execution ID of
                    [Smart](../../smart_contracts_api_reference3XX/vault/#methods-get_hook_execution_id)
                    and
                    [Supervisor](../../supervisor_contracts_api_reference3XX/vault/#methods-get_hook_execution_id)
                    Contracts Vault Object can be used as part of this key to ensure that this is
                    unique.
                """,
            ),
            types_utils.ValueSpec(
                name="account_id",
                type="str",
                docstring="""
                    The Account ID whose Schedule is amended by this
                    [HookDirective](#classes-HookDirectives).
                """,
            ),
        ]
