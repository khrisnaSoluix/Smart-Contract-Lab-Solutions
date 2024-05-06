from functools import lru_cache

from .....utils import symbols
from .....utils import types_utils


class RemoveSchedulesDirective:
    def __init__(self, *, account_id, event_types, request_id, _from_proto=False):
        if not _from_proto:
            self._spec().assert_constructor_args(
                self._registry,
                {"account_id": account_id, "event_types": event_types, "request_id": request_id},
            )

        self.account_id = account_id
        self.event_types = event_types
        self.request_id = request_id

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return types_utils.ClassSpec(
            name="RemoveSchedulesDirective",
            docstring="""
                A [HookDirective](#classes-HookDirectives) that instructs the removal of a
                Schedule. **Only available in version 3.4.0+**.
            """,
            public_attributes=cls._public_attributes(language_code),
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new RemoveSchedulesDirective",
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
                docstring="""
                    The Account ID whose Schedule is removed by this
                    [HookDirective](#classes-HookDirectives).
                """,
            ),
            types_utils.ValueSpec(
                name="event_types",
                type="List[str]",
                docstring="""
                    A list of the [EventTypes](#classes-EventType) to be removed.
                """,
            ),
            types_utils.ValueSpec(
                name="request_id",
                type="str",
                docstring="""
                    The idempotency key. The hook execution ID of
                    [Smart](../../smart_contracts_api_reference3XX/vault/#methods-get_hook_execution_id)
                    and
                    [Supervisor](../../supervisor_contracts_api_reference3XX/vault/#methods-get_hook_execution_id)
                    Contracts Vault object can be used as part of this key to ensure that this is
                    unique.
                """,
            ),
        ]
