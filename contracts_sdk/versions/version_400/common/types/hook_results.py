from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from typing import List, Dict, Iterator, Optional, Union, Type

from .account_notification_directive import AccountNotificationDirective
from .event_types import ScheduledEvent
from .parameters import OptionalValue, UnionItemValue
from .plan_notification_directive import PlanNotificationDirective
from .posting_instructions_directive import PostingInstructionsDirective
from .rejection import Rejection
from .update_account_event_type_directive import UpdateAccountEventTypeDirective
from .update_plan_event_type_directive import UpdatePlanEventTypeDirective
from .....utils import symbols, types_utils
from .....utils.exceptions import InvalidSmartContractError


def validate_account_directives(
    account_directives: Optional[List[AccountNotificationDirective]],
    posting_directives: Optional[List[PostingInstructionsDirective]],
    update_events: Optional[List[UpdateAccountEventTypeDirective]] = None,
):
    if account_directives is not None:
        _validate_account_directives(
            account_directives, AccountNotificationDirective, "account_directives"
        )
    if posting_directives is not None:
        _validate_account_directives(
            posting_directives, PostingInstructionsDirective, "posting_directives"
        )
    if update_events is None:
        return
    _validate_account_event_types(update_events)


def validate_scheduled_events(scheduled_events: Dict[str, ScheduledEvent]):
    types_utils.validate_type(scheduled_events, dict)
    for event in scheduled_events.values():
        types_utils.validate_type(event, ScheduledEvent)


def validate_plan_directives(
    plan_notification_directives: Optional[List[PlanNotificationDirective]] = None,
    update_events: Optional[List[UpdatePlanEventTypeDirective]] = None,
):
    type_hint = "PlanNotificationDirective"
    if plan_notification_directives is not None:
        iterator = types_utils.get_iterator(
            plan_notification_directives, type_hint, "plan_notification_directives"
        )
        for directive in iterator:
            types_utils.validate_type(
                directive, PlanNotificationDirective, hint=f"List[{type_hint}]"
            )
    if update_events is None:
        return
    _validate_plan_event_types(update_events)


def validate_supervisee_directives(
    supervisee_account_directives: Dict[str, List[AccountNotificationDirective]],
    supervisee_posting_directives: Dict[str, List[PostingInstructionsDirective]],
    supervisee_update_account_directives: Dict[str, List[UpdateAccountEventTypeDirective]],
):
    _validate_supervisee_directives(
        supervisee_account_directives,
        AccountNotificationDirective,
        "supervisee_account_notification_directives",
    )
    _validate_supervisee_directives(
        supervisee_posting_directives,
        PostingInstructionsDirective,
        "supervisee_posting_instructions_directives",
    )
    types_utils.validate_type(
        supervisee_update_account_directives,
        dict,
        prefix="supervisee_update_account_event_type_directives",
    )
    for directives in supervisee_update_account_directives.values():
        _validate_account_event_types(directives)


def _validate_account_directives(
    directives: Union[List[AccountNotificationDirective], List[PostingInstructionsDirective]],
    expected_class: Union[Type[AccountNotificationDirective], Type[PostingInstructionsDirective]],
    name: str,
):
    type_hint = f"{expected_class.__name__}"
    iterator = types_utils.get_iterator(directives, type_hint, name)
    for directive in iterator:
        types_utils.validate_type(directive, expected_class, hint=f"List[{type_hint}]")


def _validate_account_event_types(
    update_event_type_directives: Optional[List[UpdateAccountEventTypeDirective]],
):
    if update_event_type_directives is None:
        return
    iterator = types_utils.get_iterator(
        update_event_type_directives,
        UpdateAccountEventTypeDirective.__name__,
        "update_event_type_directives",
    )
    _validate_unique_event_type_directives(iterator, UpdateAccountEventTypeDirective)


def _validate_plan_event_types(
    update_event_type_directives: Optional[List[UpdatePlanEventTypeDirective]],
):
    if update_event_type_directives is None:
        return
    iterator = types_utils.get_iterator(
        update_event_type_directives,
        UpdatePlanEventTypeDirective.__name__,
        "update_event_type_directives",
    )
    _validate_unique_event_type_directives(iterator, UpdatePlanEventTypeDirective)


def _validate_unique_event_type_directives(
    event_type_directives_iterator: Iterator,
    event_class: Union[Type[UpdateAccountEventTypeDirective], Type[UpdatePlanEventTypeDirective]],
):
    seen_updated_event_types = set()
    for update_event_type_directive in event_type_directives_iterator:
        types_utils.validate_type(update_event_type_directive, event_class)
        event_type = update_event_type_directive.event_type
        if event_type in seen_updated_event_types:
            raise InvalidSmartContractError(
                f"Event type '{event_type}' cannot be updated more than once in a hook"
            )
        seen_updated_event_types.add(event_type)


def _validate_supervisee_directives(
    supervisee_directives: Union[
        Dict[str, List[AccountNotificationDirective]],
        Dict[str, List[PostingInstructionsDirective]],
    ],
    expected_class: Type[Union[AccountNotificationDirective, PostingInstructionsDirective]],
    hint: str,
):
    types_utils.validate_type(supervisee_directives, dict, hint=hint)
    for directives in supervisee_directives.values():
        _validate_account_directives(directives, expected_class, hint)


class DerivedParameterHookResult:
    def __init__(
        self,
        *,
        parameters_return_value: Dict[
            str, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]
        ],
    ):
        self.parameters_return_value = parameters_return_value
        self._validate_attributes()

    def _validate_attributes(self):
        types_utils.validate_type(
            self.parameters_return_value, dict, prefix="parameters_return_value"
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="DerivedParameterHookResult",
            docstring="The hook result of the `derived_parameter_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new DerivedParameterHookResult object.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="parameters_return_value",
                type="Dict[str, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]]",
                docstring="""
                A dictionary with values keyed by parameter name for all
                [derived parameters](/reference/contracts/concepts_4xx/#contract_parameters)
                defined in the Smart Contract Metadata. An entry in the dictionary needs to exist
                for all defined derived parameters. Values that are allowed to be returned by
                Parameter Shape: NumberShape: Decimal or int, StringShape: str, AccountIdShape:
                str, DenominationShape: str, DateShape: datetime, OptionalShape: OptionalValue,
                UnionShape: UnionItemValue with key in the set of valid keys of the UnionShape.
                """,
            )
        ]


class DeactivationHookResult:
    def __init__(
        self,
        *,
        account_notification_directives: Optional[List[AccountNotificationDirective]] = None,
        posting_instructions_directives: Optional[List[PostingInstructionsDirective]] = None,
        update_account_event_type_directives: Optional[
            List[UpdateAccountEventTypeDirective]
        ] = None,
        rejection: Optional[Rejection] = None,
    ):
        self.account_notification_directives = account_notification_directives or []
        self.posting_instructions_directives = posting_instructions_directives or []
        self.update_account_event_type_directives = update_account_event_type_directives or []
        self.rejection = rejection
        self._validate_attributes()

    def _validate_attributes(self):
        if self.rejection is not None:
            types_utils.validate_type(self.rejection, Rejection, prefix="rejection")
            # Either Directives or rejection can be populated, not both.
            if (
                self.account_notification_directives
                or self.posting_instructions_directives
                or self.update_account_event_type_directives
            ):
                raise InvalidSmartContractError(
                    "DeactivationHookResult allows the population of directives or rejection, "
                    "but not both"
                )
        validate_account_directives(
            self.account_notification_directives,
            self.posting_instructions_directives,
            self.update_account_event_type_directives,
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="DeactivationHookResult",
            docstring="The hook result of the `deactivation_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="""
                Constructs a new DeactivationHookResult object. It allows the population of
                directives or rejection, but not both.
                """,
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="account_notification_directives",
                type="Optional[List[AccountNotificationDirective]]",
                docstring="""
                A list of [AccountNotificationDirective](#classes-AccountNotificationDirective)s
                to be instructed by the hook.
                """,
            ),
            types_utils.ValueSpec(
                name="posting_instructions_directives",
                type="Optional[List[PostingInstructionsDirective]]",
                docstring="""
                A list of [PostingInstructionsDirective](#classes-PostingInstructionsDirective)s
                to be instructed by the hook.
                """,
            ),
            types_utils.ValueSpec(
                name="update_account_event_type_directives",
                type="Optional[List[UpdateAccountEventTypeDirective]]",
                docstring="""
                A list of [UpdateAccountEventTypeDirective](#classes-UpdateAccountEventTypeDirective)s
                to be instructed by the hook.
                """,  # noqa E501
            ),
            types_utils.ValueSpec(
                name="rejection",
                type="Optional[Rejection]",
                docstring="""
                A Hook [Rejection](#classes-Rejection). If returned, the account status is updated
                to `ACCOUNT_STATUS_PENDING_CLOSURE.`
                """,
            ),
        ]


class ActivationHookResult:
    def __init__(
        self,
        *,
        account_notification_directives: Optional[List[AccountNotificationDirective]] = None,
        posting_instructions_directives: Optional[List[PostingInstructionsDirective]] = None,
        scheduled_events_return_value: Optional[Dict[str, ScheduledEvent]] = None,
    ):
        self.account_notification_directives = account_notification_directives or []
        self.posting_instructions_directives = posting_instructions_directives or []
        self.scheduled_events_return_value = scheduled_events_return_value or {}
        self._validate_attributes()

    def _validate_attributes(self):
        validate_account_directives(
            self.account_notification_directives, self.posting_instructions_directives
        )
        validate_scheduled_events(self.scheduled_events_return_value)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ActivationHookResult",
            docstring="The hook result of the `activation_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new ActivationHookResult object",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="account_notification_directives",
                type="Optional[List[AccountNotificationDirective]]",
                docstring="""
                A list of [AccountNotificationDirective](#classes-AccountNotificationDirective)s
                to be instructed by the hook.
                """,
            ),
            types_utils.ValueSpec(
                name="posting_instructions_directives",
                type="Optional[List[PostingInstructionsDirective]]",
                docstring="""
                A list of [PostingInstructionsDirective](#classes-PostingInstructionsDirective)s
                to be instructed by the hook.
                """,
            ),
            types_utils.ValueSpec(
                name="scheduled_events_return_value",
                type="Optional[Dict[str, ScheduledEvent]]",
                docstring="""
                A dictionary containing [ScheduledEvent](#classes-ScheduledEvent)s by name returned
                by the hook.
                """,
            ),
        ]


class PostParameterChangeHookResult:
    def __init__(
        self,
        *,
        account_notification_directives: Optional[List[AccountNotificationDirective]] = None,
        posting_instructions_directives: Optional[List[PostingInstructionsDirective]] = None,
        update_account_event_type_directives: Optional[
            List[UpdateAccountEventTypeDirective]
        ] = None,
    ):
        self.account_notification_directives = account_notification_directives or []
        self.posting_instructions_directives = posting_instructions_directives or []
        self.update_account_event_type_directives = update_account_event_type_directives or []
        self._validate_attributes()

    def _validate_attributes(self):
        validate_account_directives(
            self.account_notification_directives,
            self.posting_instructions_directives,
            self.update_account_event_type_directives,
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="PostParameterChangeHookResult",
            docstring="The hook result of the `post_parameter_change_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new PostParameterChangeHookResult object",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="account_notification_directives",
                type="Optional[List[AccountNotificationDirective]]",
                docstring="""
                A list of [AccountNotificationDirective](#classes-AccountNotificationDirective)s
                to be instructed by the hook.
                """,
            ),
            types_utils.ValueSpec(
                name="posting_instructions_directives",
                type="Optional[List[PostingInstructionsDirective]]",
                docstring="""
                A list of [PostingInstructionsDirective](#classes-PostingInstructionsDirective)s
                to be instructed by the hook.
                """,
            ),
            types_utils.ValueSpec(
                name="update_account_event_type_directives",
                type="Optional[List[UpdateAccountEventTypeDirective]]",
                docstring="""
                A list of [UpdateAccountEventTypeDirective](#classes-UpdateAccountEventTypeDirective)s
                to be instructed by the hook.
                """,  # noqa E501
            ),
        ]


class PostPostingHookResult:
    def __init__(
        self,
        *,
        account_notification_directives: Optional[List[AccountNotificationDirective]] = None,
        posting_instructions_directives: Optional[List[PostingInstructionsDirective]] = None,
        update_account_event_type_directives: Optional[
            List[UpdateAccountEventTypeDirective]
        ] = None,
        _from_proto: Optional[bool] = False,
    ):
        self.account_notification_directives = account_notification_directives or []
        self.posting_instructions_directives = posting_instructions_directives or []
        self.update_account_event_type_directives = update_account_event_type_directives or []
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        validate_account_directives(
            self.account_notification_directives,
            self.posting_instructions_directives,
            self.update_account_event_type_directives,
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="PostPostingHookResult",
            docstring="The hook result of the `post_posting_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new PostPostingHookResult object",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="account_notification_directives",
                type="Optional[List[AccountNotificationDirective]]",
                docstring="""
                A list of [AccountNotificationDirective](#classes-AccountNotificationDirective)s
                to be instructed by the hook.
                """,
            ),
            types_utils.ValueSpec(
                name="posting_instructions_directives",
                type="Optional[List[PostingInstructionsDirective]]",
                docstring="""
                A list of [PostingInstructionsDirective](#classes-PostingInstructionsDirective)s
                to be instructed by the hook.
                """,
            ),
            types_utils.ValueSpec(
                name="update_account_event_type_directives",
                type="Optional[List[UpdateAccountEventTypeDirective]]",
                docstring="""
                A list of [UpdateAccountEventTypeDirective](#classes-UpdateAccountEventTypeDirective)s
                to be instructed by the hook.
                """,  # noqa E501
            ),
        ]


class PreParameterChangeHookResult:
    def __init__(self, *, rejection: Optional[Rejection] = None):
        self.rejection = rejection
        self._validate_attributes()

    def _validate_attributes(self):
        if self.rejection is not None:
            types_utils.validate_type(self.rejection, Rejection, prefix="rejection")

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="PreParameterChangeHookResult",
            docstring="The hook result of the `pre_parameter_change_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new PreParameterChangeHookResult object",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="rejection",
                type="Optional[Rejection]",
                docstring="""
                A Hook [Rejection](#classes-Rejection). If returned, the parameter update is
                rejected.
                """,
            )
        ]


class PrePostingHookResult:
    def __init__(
        self,
        *,
        rejection: Optional[Rejection] = None,
        _from_proto: Optional[bool] = False,
    ):
        self.rejection = rejection
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        if self.rejection is not None:
            types_utils.validate_type(self.rejection, Rejection, prefix="rejection")

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="PrePostingHookResult",
            docstring="The hook result of the `pre_posting_hook`",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new PrePostingHookResult object",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="rejection",
                type="Optional[Rejection]",
                docstring="""
                A Hook [Rejection](#classes-Rejection). If returned, the proposed Postings will
                not be committed.
                """,
            )
        ]


class ScheduledEventHookResult:
    def __init__(
        self,
        *,
        account_notification_directives: Optional[List[AccountNotificationDirective]] = None,
        posting_instructions_directives: Optional[List[PostingInstructionsDirective]] = None,
        update_account_event_type_directives: Optional[
            List[UpdateAccountEventTypeDirective]
        ] = None,
        _from_proto: Optional[bool] = False,
    ):
        self.account_notification_directives = account_notification_directives or []
        self.posting_instructions_directives = posting_instructions_directives or []
        self.update_account_event_type_directives = update_account_event_type_directives or []
        if not _from_proto:
            self._validate_attributes()

    def _validate_attributes(self):
        validate_account_directives(
            self.account_notification_directives,
            self.posting_instructions_directives,
            self.update_account_event_type_directives,
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ScheduledEventHookResult",
            docstring="The hook result of the `scheduled_event_hook`",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="account_notification_directives",
                type="Optional[List[AccountNotificationDirective]]",
                docstring="""
                A list of [AccountNotificationDirective](#classes-AccountNotificationDirective)s
                to be instructed by the hook.
                """,
            ),
            types_utils.ValueSpec(
                name="posting_instructions_directives",
                type="Optional[List[PostingInstructionsDirective]]",
                docstring="""
                A list of [PostingInstructionsDirective](#classes-PostingInstructionsDirective)s
                to be instructed by the hook.
                """,
            ),
            types_utils.ValueSpec(
                name="update_account_event_type_directives",
                type="Optional[List[UpdateAccountEventTypeDirective]]",
                docstring="""
                A list of [UpdateAccountEventTypeDirective](#classes-UpdateAccountEventTypeDirective)s
                to be instructed by the hook.
                """,  # noqa E501
            ),
        ]


class SupervisorPostPostingHookResult:
    def __init__(
        self,
        *,
        # Plan Directives
        plan_notification_directives: Optional[List[PlanNotificationDirective]] = None,
        update_plan_event_type_directives: Optional[List[UpdatePlanEventTypeDirective]] = None,
        # Supervisee Directives
        supervisee_account_notification_directives: Optional[
            Dict[str, List[AccountNotificationDirective]]
        ] = None,
        supervisee_posting_instructions_directives: Optional[
            Dict[str, List[PostingInstructionsDirective]]
        ] = None,
        supervisee_update_account_event_type_directives: Optional[
            Dict[str, List[UpdateAccountEventTypeDirective]]
        ] = None,
    ):
        self.plan_notification_directives = plan_notification_directives or []
        self.update_plan_event_type_directives = update_plan_event_type_directives or []
        self.supervisee_account_notification_directives = (
            supervisee_account_notification_directives or defaultdict(list)
        )
        self.supervisee_posting_instructions_directives = (
            supervisee_posting_instructions_directives or defaultdict(list)
        )
        self.supervisee_update_account_event_type_directives = (
            supervisee_update_account_event_type_directives or defaultdict(list)
        )
        self._validate_attributes()

    def _validate_attributes(self):
        validate_plan_directives(
            self.plan_notification_directives, self.update_plan_event_type_directives
        )
        validate_supervisee_directives(
            self.supervisee_account_notification_directives,
            self.supervisee_posting_instructions_directives,
            self.supervisee_update_account_event_type_directives,
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SupervisorPostPostingHookResult",
            docstring="The hook result of the Supervisor `post_posting_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SupervisorPostPostingHookResult object.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="plan_notification_directives",
                type="Optional[List[PlanNotificationDirective]]",
                docstring="""
                A list of [PlanNotificationDirective](#classes-PlanNotificationDirective)s
                to be instructed by the Supervisor hook.
                """,
            ),
            types_utils.ValueSpec(
                name="update_plan_event_type_directives",
                type="Optional[List[UpdatePlanEventTypeDirective]]",
                docstring="""
                A list of [UpdatePlanEventTypeDirective](#classes-UpdatePlanEventTypeDirective)s
                to be instructed by the Supervisor hook.
                """,
            ),
            types_utils.ValueSpec(
                name="supervisee_account_notification_directives",
                type="Optional[Dict[str, List[AccountNotificationDirective]]]",
                docstring="""
                A dictionary containing Lists of
                [AccountNotificationDirective](#classes-AccountNotificationDirective)s
                keyed by Supervisee account id, returned by the Supervisor hook.
                """,
            ),
            types_utils.ValueSpec(
                name="supervisee_posting_instructions_directives",
                type="Optional[Dict[str, List[PostingInstructionsDirective]]]",
                docstring="""
                A dictionary containing Lists of
                [PostingInstructionsDirective](#classes-PostingInstructionsDirective)s
                keyed by Supervisee account id, returned by the Supervisor hook.
                """,
            ),
            types_utils.ValueSpec(
                name="supervisee_update_account_event_type_directives",
                type="Optional[Dict[str, List[UpdateAccountEventTypeDirective]]]",
                docstring="""
                A dictionary containing Lists of
                [UpdateAccountEventTypeDirective](#classes-UpdateAccountEventTypeDirective)s
                keyed by Supervisee account id, returned by the Supervisor hook.
                """,
            ),
        ]


class SupervisorPrePostingHookResult:
    def __init__(self, *, rejection: Optional[Rejection] = None):
        self.rejection = rejection
        self._validate_attributes()

    def _validate_attributes(self):
        if self.rejection is not None:
            types_utils.validate_type(self.rejection, Rejection, prefix="rejection")

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SupervisorPrePostingHookResult",
            docstring="The hook result of the Supervisor `pre_posting_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SupervisorPrePostingHookResult object",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="rejection",
                type="Optional[Rejection]",
                docstring="""
                A Hook [Rejection](#classes-Rejection). If returned, the proposed Postings will
                not be committed.
                """,
            )
        ]


class SupervisorActivationHookResult:
    def __init__(
        self,
        *,
        scheduled_events_return_value: Optional[Dict[str, ScheduledEvent]] = None,
    ):
        self.scheduled_events_return_value = scheduled_events_return_value or {}
        self._validate_attributes()

    def _validate_attributes(self):
        validate_scheduled_events(self.scheduled_events_return_value)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SupervisorActivationHookResult",
            docstring="The hook result of the Supervisor `activation_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SupervisorActivationHookResult object.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="scheduled_events_return_value",
                type="Optional[Dict[str, ScheduledEvent]]",
                docstring="""
                A dictionary containing [ScheduledEvent](#classes-ScheduledEvent)s keyed by name
                returned by the Supervisor hook.
                """,
            ),
        ]


class SupervisorConversionHookResult:
    def __init__(
        self,
        *,
        scheduled_events_return_value: Optional[Dict[str, ScheduledEvent]] = None,
    ):
        self.scheduled_events_return_value = scheduled_events_return_value or {}
        self._validate_attributes()

    def _validate_attributes(self):
        validate_scheduled_events(self.scheduled_events_return_value)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SupervisorConversionHookResult",
            docstring="The hook result of the Supervisor `conversion_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SupervisorConversionHookResult object.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="scheduled_events_return_value",
                type="Optional[Dict[str, ScheduledEvent]]",
                docstring="""
                A dictionary containing [ScheduledEvent](#classes-ScheduledEvent)s keyed by name
                returned by the Supervisor hook.
                For any new `event_types` in this Contract returned in this mapping, you cannot
                set `ScheduledEvent` `start_datetime` to before the hook `effective_datetime`.
                For any `event_types` that exist in the previous Contract and are returned in
                this mapping, the `ScheduledEvent` `start_datetime` is disregarded and defaults
                to the last run time of the existing `event_type` schedule. Because of this,
                the start_datetime for the existing schedules must be set to None or remain
                unchanged, as any other values will result in an error.
                """,
            ),
        ]


class SupervisorScheduledEventHookResult:
    def __init__(
        self,
        *,
        # Plan Directives
        plan_notification_directives: Optional[List[PlanNotificationDirective]] = None,
        update_plan_event_type_directives: Optional[List[UpdatePlanEventTypeDirective]] = None,
        # Supervisee Directives
        supervisee_account_notification_directives: Optional[
            Dict[str, List[AccountNotificationDirective]]
        ] = None,
        supervisee_posting_instructions_directives: Optional[
            Dict[str, List[PostingInstructionsDirective]]
        ] = None,
        supervisee_update_account_event_type_directives: Optional[
            Dict[str, List[UpdateAccountEventTypeDirective]]
        ] = None,
    ):
        self.plan_notification_directives = plan_notification_directives or []
        self.update_plan_event_type_directives = update_plan_event_type_directives or []
        self.supervisee_account_notification_directives = (
            supervisee_account_notification_directives or defaultdict(list)
        )
        self.supervisee_posting_instructions_directives = (
            supervisee_posting_instructions_directives or defaultdict(list)
        )
        self.supervisee_update_account_event_type_directives = (
            supervisee_update_account_event_type_directives or defaultdict(list)
        )
        self._validate_attributes()

    def _validate_attributes(self):
        validate_plan_directives(
            self.plan_notification_directives, self.update_plan_event_type_directives
        )
        validate_supervisee_directives(
            self.supervisee_account_notification_directives,
            self.supervisee_posting_instructions_directives,
            self.supervisee_update_account_event_type_directives,
        )

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="SupervisorScheduledEventHookResult",
            docstring="The hook result of the Supervisor `scheduled_event_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new SupervisorScheduledEventHookResult object.",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="plan_notification_directives",
                type="Optional[List[PlanNotificationDirective]]",
                docstring="""
                A list of [PlanNotificationDirective](#classes-PlanNotificationDirective)s
                to be instructed by the Supervisor hook.
                """,
            ),
            types_utils.ValueSpec(
                name="update_plan_event_type_directives",
                type="Optional[List[UpdatePlanEventTypeDirective]]",
                docstring="""
                A list of [UpdatePlanEventTypeDirective](#classes-UpdatePlanEventTypeDirective)s
                to be instructed by the Supervisor hook.
                """,
            ),
            types_utils.ValueSpec(
                name="supervisee_account_notification_directives",
                type="Optional[Dict[str, List[AccountNotificationDirective]]]",
                docstring="""
                A dictionary containing Lists of
                [AccountNotificationDirective](#classes-AccountNotificationDirective)s
                keyed by Supervisee account id, returned by the Supervisor hook.
                """,
            ),
            types_utils.ValueSpec(
                name="supervisee_posting_instructions_directives",
                type="Optional[Dict[str, List[PostingInstructionsDirective]]]",
                docstring="""
                A dictionary containing Lists of
                [PostingInstructionsDirective](#classes-PostingInstructionsDirective)s
                keyed by Supervisee account id, returned by the Supervisor hook.
                """,
            ),
            types_utils.ValueSpec(
                name="supervisee_update_account_event_type_directives",
                type="Optional[Dict[str, List[UpdateAccountEventTypeDirective]]]",
                docstring="""
                A dictionary containing Lists of
                [UpdateAccountEventTypeDirective](#classes-UpdateAccountEventTypeDirective)s
                keyed by Supervisee account id, returned by the Supervisor hook.
                """,
            ),
        ]


class ConversionHookResult:
    def __init__(
        self,
        *,
        account_notification_directives: Optional[List[AccountNotificationDirective]] = None,
        posting_instructions_directives: Optional[List[PostingInstructionsDirective]] = None,
        scheduled_events_return_value: Optional[Dict[str, ScheduledEvent]] = None,
    ):
        self.account_notification_directives = account_notification_directives or []
        self.posting_instructions_directives = posting_instructions_directives or []
        self.scheduled_events_return_value = scheduled_events_return_value or {}
        self._validate_attributes()

    def _validate_attributes(self):
        validate_account_directives(
            self.account_notification_directives, self.posting_instructions_directives
        )
        validate_scheduled_events(self.scheduled_events_return_value)

    @classmethod
    @lru_cache()
    def _spec(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return types_utils.ClassSpec(
            name="ConversionHookResult",
            docstring="The hook result of the `conversion_hook`.",
            public_attributes=cls._public_attributes(language_code),  # noqa: SLF001
            constructor=types_utils.ConstructorSpec(
                docstring="Constructs a new ConversionHookResult object",
                args=cls._public_attributes(language_code),  # noqa: SLF001
            ),
            public_methods=[],
        )

    @classmethod
    @lru_cache()
    def _public_attributes(cls, language_code=symbols.Languages.ENGLISH):
        if language_code != symbols.Languages.ENGLISH:
            raise ValueError("Language not supported")

        return [
            types_utils.ValueSpec(
                name="account_notification_directives",
                type="Optional[List[AccountNotificationDirective]]",
                docstring="""
                A list of [AccountNotificationDirective](#classes-AccountNotificationDirective)s
                to be instructed by the hook.
                """,
            ),
            types_utils.ValueSpec(
                name="posting_instructions_directives",
                type="Optional[List[PostingInstructionsDirective]]",
                docstring="""
                A list of [PostingInstructionsDirective](#classes-PostingInstructionsDirective)s
                to be instructed by the hook.
                """,
            ),
            types_utils.ValueSpec(
                name="scheduled_events_return_value",
                type="Optional[Dict[str, ScheduledEvent]]",
                docstring="""
                A dictionary containing [ScheduledEvent](#classes-ScheduledEvent)s by name returned
                by the hook.
                For any new `event_types` in this Contract returned in this mapping, you cannot
                set `ScheduledEvent` `start_datetime` to before the hook `effective_datetime`.
                For any `event_types` that exist in the previous Contract and are returned in
                this mapping, the `ScheduledEvent` `start_datetime` is disregarded and defaults
                to the last run time of the existing `event_type` schedule. Because of this,
                the start_datetime for the existing schedules must be set to None or remain
                unchanged, as any other values will result in an error.
                """,
            ),
        ]
