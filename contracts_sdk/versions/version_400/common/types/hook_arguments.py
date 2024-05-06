from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from typing import Dict, Optional, Union
from .....utils import symbols
from .....utils import types_utils
from .....utils.timezone_utils import validate_timezone_is_utc
from .event_types import (  # noqa: E501
    ScheduledEvent,
)
from .parameters import (  # noqa: E501
    OptionalValue,
    UnionItemValue,
)
from .postings import (  # noqa: E501
    _PITypes_str,
    ClientTransaction,
)


class HookArguments:
    def __init__(
        self,
        effective_datetime: datetime,
        _from_proto: bool = False,
    ):
        self.effective_datetime = effective_datetime
        if not _from_proto:
            self._validate_hook_attributes()

    def _validate_hook_attributes(self):
        validate_timezone_is_utc(
            self.effective_datetime,
            "effective_datetime",
            self.__repr__(),
        )

    def __repr__(self):
        return "HookArguments"

    def __eq__(self, other) -> bool:
        if type(self) is type(other):
            return self.__dict__ == other.__dict__
        return False

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="effective_datetime",
                type="datetime",
                docstring=(
                    "The logical datetime the hook is being run against. "
                    "Must be a timezone-aware UTC datetime using the ZoneInfo class."
                ),
            )
        ]


class DeactivationHookArguments(HookArguments):
    def __repr__(self):
        return "DeactivationHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="DeactivationHookArguments",
            docstring="The hook arguments of `deactivation_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new DeactivationHookArguments object.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )


class DerivedParameterHookArguments(HookArguments):
    def __repr__(self):
        return "DerivedParameterHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="DerivedParameterHookArguments",
            docstring="The hook arguments of the `derived_parameter_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new DerivedParameterHookArguments object.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )


class ActivationHookArguments(HookArguments):
    def __repr__(self):
        return "ActivationHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ActivationHookArguments",
            docstring="The hook arguments of `activation_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new ActivationHookArguments object.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )


class ConversionHookArguments(HookArguments):
    def __init__(
        self,
        effective_datetime: datetime,
        existing_schedules: Dict[str, ScheduledEvent],
    ):
        super().__init__(effective_datetime)
        self.existing_schedules = existing_schedules

    def __repr__(self):
        return "ConversionHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ConversionHookArguments",
            docstring="The hook arguments of `conversion_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new ConversionHookArguments object.",
                args=super()._public_attributes(language_code)
                + cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return super()._public_attributes(language_code) + [
            types_utils.ValueSpec(
                name="existing_schedules",
                type="Dict[str, ScheduledEvent]",
                docstring="""
                    The existing ScheduledEvents associated with the contract,
                    which may be modified by the hook.
                """,
            ),
        ]


class PostParameterChangeHookArguments(HookArguments):
    def __init__(
        self,
        effective_datetime: datetime,
        old_parameter_values: Dict[
            str, Union[datetime, Decimal, str, OptionalValue, UnionItemValue, int]
        ],
        updated_parameter_values: Dict[
            str, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]
        ],
    ):
        super().__init__(effective_datetime)
        self.old_parameter_values = old_parameter_values
        self.updated_parameter_values = updated_parameter_values

    def __repr__(self):
        return "PostParameterChangeHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="PostParameterChangeHookArguments",
            docstring="The hook arguments of `post_parameter_change_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new PostParameterChangeHookArguments object.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return super()._public_attributes(language_code) + [
            types_utils.ValueSpec(
                name="old_parameter_values",
                type="Dict[str, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]",
                docstring="All the old parameter values prior to the change.",
            ),
            types_utils.ValueSpec(
                name="updated_parameter_values",
                type="Dict[str, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]",
                docstring="Only the updated parameter values after the change.",
            ),
        ]


class PostPostingHookArguments(HookArguments):
    def __init__(
        self,
        effective_datetime: datetime,
        posting_instructions: _PITypes_str,  # type: ignore[valid-type]
        client_transactions: Dict[str, ClientTransaction],
    ):
        super().__init__(effective_datetime)
        self.posting_instructions = posting_instructions
        self.client_transactions = client_transactions

    def __repr__(self):
        return "PostPostingHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="PostPostingHookArguments",
            docstring="The hook arguments of `post_posting_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new PostPostingHookArguments object.",
                args=super()._public_attributes(language_code)
                + cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return super()._public_attributes(language_code) + [
            types_utils.ValueSpec(
                name="posting_instructions",
                type=f"{_PITypes_str}",
                docstring="""
                    The list of posting instructions that have just been atomically committed
                    to the ledger.
                """,
            ),
            types_utils.ValueSpec(
                name="client_transactions",
                type="Dict[str, ClientTransaction]",
                docstring="""
                    The ClientTransactions that are affected by the posting instructions
                    that have just been committed. Returns a map of `unique_client_transaction_id`
                    to a [ClientTransaction](#classes-ClientTransaction) object, where the
                    `unique_client_transaction_id` is the globally unique ID
                    of the ClientTransaction.
                    Note that each posting instruction class instance
                    has the read-only `unique_client_transaction_id` attribute, which represents
                    the ClientTransaction that a posting instruction is impacting. However,
                    this value is not deterministic and therefore is
                    not guaranteed to be consistent between different contract executions for
                    the same ClientTransaction.
                """,
            ),
        ]


class PrePostingHookArguments(HookArguments):
    def __init__(
        self,
        effective_datetime: datetime,
        posting_instructions: _PITypes_str,  # type: ignore[valid-type]
        client_transactions: dict[str, ClientTransaction],
    ):
        super().__init__(effective_datetime)
        self.posting_instructions = posting_instructions
        self.client_transactions = client_transactions

    def __repr__(self):
        return "PrePostingHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="PrePostingHookArguments",
            docstring="The hook arguments of `pre_posting_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new PrePostingHookArguments object.",
                args=super()._public_attributes(language_code)
                + cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return super()._public_attributes(language_code) + [
            types_utils.ValueSpec(
                name="posting_instructions",
                type=f"{_PITypes_str}",
                docstring="""
                    The proposed list of posting instructions to be
                    committed to the ledger.
                """,
            ),
            types_utils.ValueSpec(
                name="client_transactions",
                type="Dict[str, ClientTransaction]",
                docstring="""
                    The ClientTransactions that are affected by the posting instructions
                    to be committed. Returns a map of `unique_client_transaction_id`
                    to a [ClientTransaction](#classes-ClientTransaction) object, where the
                    `unique_client_transaction_id` is the globally unique ID
                    of the ClientTransaction.
                    Note that each posting instruction class instance
                    has the read-only `unique_client_transaction_id` attribute, which represents
                    the ClientTransaction that a posting instruction is impacting. However,
                    this value is not deterministic and therefore is
                    not guaranteed to be consistent between different contract executions for
                    the same ClientTransaction.
                """,
            ),
        ]


class PreParameterChangeHookArguments(HookArguments):
    def __init__(
        self,
        effective_datetime: datetime,
        updated_parameter_values: Dict[
            str, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]
        ],
    ):

        super().__init__(effective_datetime)
        self.updated_parameter_values = updated_parameter_values

    def __repr__(self):
        return "PreParameterChangeHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="PreParameterChangeHookArguments",
            docstring="The hook arguments of `pre_parameter_change_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new PreParameterChangeHookArguments object.",
                args=super()._public_attributes(language_code)
                + cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return super()._public_attributes(language_code) + [
            types_utils.ValueSpec(
                name="updated_parameter_values",
                type="Dict[str, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]",
                docstring="""
                    The proposed instance level parameter updates. This is a mapping of parameter
                    name to parameter value. These values are pending and have not yet been
                    committed.
                """,
            ),
        ]


class ScheduledEventHookArguments(HookArguments):
    def __init__(
        self,
        effective_datetime: datetime,
        event_type: str,
        pause_at_datetime: Optional[datetime] = None,
        _from_proto: bool = False,
    ):
        super().__init__(effective_datetime)
        self.event_type = event_type
        self.pause_at_datetime = pause_at_datetime
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        if self.pause_at_datetime is not None:
            types_utils.validate_type(
                self.pause_at_datetime,
                datetime,
                prefix="pause_at_datetime",
            )
            validate_timezone_is_utc(
                self.pause_at_datetime,
                "pause_at_datetime",
                "ScheduledEventHookArguments",
            )

    def __repr__(self):
        return "ScheduledEventHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ScheduledEventHookArguments",
            docstring="The hook arguments of `scheduled_event_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new ScheduledEventHookArguments object.",
                args=super()._public_attributes(language_code)
                + cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return super()._public_attributes(language_code) + [
            types_utils.ValueSpec(
                name="event_type",
                type="str",
                docstring="""
                    The event type for which the hook is being called. Event types are defined in
                    `activation_hook` and `conversion_hook`.
                """,
            ),
            types_utils.ValueSpec(
                name="pause_at_datetime",
                type="Optional[datetime]",
                docstring="""
                    The `test_pause_at_datetime` attribute value set in
                    [AccountScheduleTag](/api/core_api/#Account_schedule_tags-AccountScheduleTag)
                    to pause the account scheduled events.
                    If multiple tags are set with different values for
                    `test_pause_at_datetime`, the earliest datetime is used.
                    Defaults to None, if the attribute is not set or the account
                    [SmartContractEventType](#classes-SmartContractEventType) has no
                    `scheduler_tag_ids` applied.
                    Must be a timezone-aware UTC datetime using the ZoneInfo class.
                """,
            ),
        ]


class SupervisorPostPostingHookArguments(HookArguments):
    def __init__(
        self,
        effective_datetime: datetime,
        supervisee_posting_instructions: Dict[str, _PITypes_str],  # type: ignore[valid-type]
        supervisee_client_transactions: Dict[str, Dict[str, ClientTransaction]],
    ):
        super().__init__(effective_datetime)
        self.supervisee_posting_instructions = supervisee_posting_instructions
        self.supervisee_client_transactions = supervisee_client_transactions

    def __repr__(self):
        return "SupervisorPostPostingHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SupervisorPostPostingHookArguments",
            docstring="The hook arguments of `post_posting_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SupervisorPostPostingHookArguments object.",
                args=super()._public_attributes(language_code)
                + cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")
        return super()._public_attributes(language_code) + [
            types_utils.ValueSpec(
                name="supervisee_posting_instructions",
                type=f"Dict[str, {_PITypes_str}]",
                docstring="""
                    Mapping of Supervisee Account ID to committed posting instructions list. The
                    list contains successfully committed posting instructions targetting
                    the supervisee.
                """,
            ),
            types_utils.ValueSpec(
                name="supervisee_client_transactions",
                type="Dict[str, Dict[str, ClientTransaction]]",
                docstring="""
                    Mapping of Supervisee Account ID to the ClientTransactions
                    that are affected by the posting instructions which just have been
                    committed. The ClientTransactions for each Supervisee is itself a map
                    of `unique_client_transaction_id` to a
                    [ClientTransaction](#classes-ClientTransaction) object, where the
                    `unique_client_transaction_id` is the globally unique ID
                    of the ClientTransaction.
                    Note that each posting instruction class instance
                    has the read-only `unique_client_transaction_id` attribute, which represents
                    the ClientTransaction that a posting instruction is impacting. However,
                    this value is not deterministic and therefore is
                    not guaranteed to be consistent between different contract executions for
                    the same ClientTransaction.
                """,
            ),
        ]


class SupervisorPrePostingHookArguments(HookArguments):
    def __init__(
        self,
        effective_datetime: datetime,
        supervisee_posting_instructions: Dict[str, _PITypes_str],  # type: ignore[valid-type]
        supervisee_client_transactions: Dict[str, Dict[str, ClientTransaction]],
    ):
        super().__init__(effective_datetime)
        self.supervisee_posting_instructions = supervisee_posting_instructions
        self.supervisee_client_transactions = supervisee_client_transactions

    def __repr__(self):
        return "SupervisorPrePostingHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SupervisorPrePostingHookArguments",
            docstring="The hook arguments of `pre_posting_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SupervisorPrePostingHookArguments object.",
                args=super()._public_attributes(language_code)
                + cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return super()._public_attributes(language_code) + [
            types_utils.ValueSpec(
                name="supervisee_posting_instructions",
                type=f"Dict[str, {_PITypes_str}]",
                docstring="""
                    Mapping of Supervisee Account ID to proposed list of
                    posting instructions to be committed to the ledger.
                """,
            ),
            types_utils.ValueSpec(
                name="supervisee_client_transactions",
                type="Dict[str, Dict[str, ClientTransaction]]",
                docstring="""
                    Mapping of Supervisee Account ID to the ClientTransactions
                    that are affected by the proposed posting instructions to be
                    committed to the ledger. The ClientTransactions for each Supervisee is
                    itself a map of `unique_client_transaction_id` to a
                    [ClientTransaction](#classes-ClientTransaction) object, where the
                    `unique_client_transaction_id` is the globally unique ID
                    of the ClientTransaction.
                    Note that each posting instruction class instance
                    has the read-only `unique_client_transaction_id` attribute, which represents
                    the ClientTransaction that a posting instruction is impacting. However,
                    this value is not deterministic and therefore is
                    not guaranteed to be consistent between different contract executions for
                    the same ClientTransaction.
                """,
            ),
        ]


class SupervisorScheduledEventHookArguments(HookArguments):
    def __init__(
        self,
        effective_datetime: datetime,
        event_type: str,
        supervisee_pause_at_datetime: Dict[str, Optional[datetime]],
        pause_at_datetime: Optional[datetime] = None,
        _from_proto: bool = False,
    ):
        super().__init__(effective_datetime)
        self.event_type = event_type
        self.supervisee_pause_at_datetime = supervisee_pause_at_datetime
        self.pause_at_datetime = pause_at_datetime
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        if self.pause_at_datetime is not None:
            types_utils.validate_type(
                self.pause_at_datetime,
                datetime,
                prefix="pause_at_datetime",
            )
            validate_timezone_is_utc(
                self.pause_at_datetime,
                "pause_at_datetime",
                "SupervisorScheduledEventHookArguments",
            )
        for key, supervisee_datetime in self.supervisee_pause_at_datetime.items():
            if supervisee_datetime is not None:
                types_utils.validate_type(
                    supervisee_datetime,
                    datetime,
                    prefix="supervisee_pause_at_datetime['" + key + "']",
                )
                validate_timezone_is_utc(
                    self.supervisee_pause_at_datetime[key],
                    "supervisee_pause_at_datetime['" + key + "']",
                    "SupervisorScheduledEventHookArguments",
                )

    def __repr__(self):
        return "SupervisorScheduledEventHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SupervisorScheduledEventHookArguments",
            docstring="The hook arguments of `scheduled_event_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SupervisorScheduledEventHookArguments object.",
                args=super()._public_attributes(language_code)
                + cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return super()._public_attributes(language_code) + [
            types_utils.ValueSpec(
                name="event_type",
                type="str",
                docstring="""
                    The event type for which the hook is being called. Event types are defined in
                    `activation_hook` and `conversion_hook`.
                """,
            ),
            types_utils.ValueSpec(
                name="pause_at_datetime",
                type="Optional[datetime]",
                docstring="""
                    The `test_pause_at_datetime` attribute value set in
                    [AccountScheduleTag](/api/core_api/#Account_schedule_tags-AccountScheduleTag)
                    to pause the account scheduled events.
                    If multiple tags are set with different values for
                    `test_pause_at_datetime`, the earliest datetime is used.
                    Defaults to None, if the attribute is not set or the account
                    [SmartContractEventType](#classes-SmartContractEventType) has no
                    `scheduler_tag_ids` applied.
                    Must be a timezone-aware UTC datetime using the ZoneInfo class.
                """,
            ),
            types_utils.ValueSpec(
                name="supervisee_pause_at_datetime",
                type="Dict[str, Optional[datetime]]",
                docstring="""
                    Mapping of Supervisee Account ID to `test_pause_at_datetime` attribute value
                    set in
                    [AccountScheduleTag](/api/core_api/#Account_schedule_tags-AccountScheduleTag)
                    to pause the account scheduled events. If multiple tags
                    are set with different values for `test_pause_at_datetime`, the earliest
                    datetime is used. Defaults to None, if the attribute is not set or the
                    account [SmartContractEventType](#classes-SmartContractEventType) has no
                    `scheduler_tag_ids` applied.
                    Supervisee datetimes must be timezone-aware and UTC using the ZoneInfo class.
                """,
            ),
        ]


class SupervisorActivationHookArguments(HookArguments):
    def __repr__(self):
        return "SupervisorActivationHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SupervisorActivationHookArguments",
            docstring="The hook arguments of `activation_hook` for supervisors.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SupervisorActivationHookArguments object.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
        )


class SupervisorConversionHookArguments(HookArguments):
    def __init__(
        self,
        effective_datetime: datetime,
        existing_schedules: Dict[str, ScheduledEvent],
    ):
        super().__init__(effective_datetime)
        self.existing_schedules = existing_schedules

    def __repr__(self):
        return "SupervisorConversionHookArguments"

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SupervisorConversionHookArguments",
            docstring="The hook arguments of `conversion_hook` for supervisors.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SupervisorConversionHookArguments object.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        public_attributes = super()._public_attributes(language_code)
        return public_attributes + [
            types_utils.ValueSpec(
                name="existing_schedules",
                type="Dict[str, ScheduledEvent]",
                docstring="""
                    The existing ScheduledEvents associated with the contract,
                    which may be modified by the hook.
                """,
            ),
        ]
