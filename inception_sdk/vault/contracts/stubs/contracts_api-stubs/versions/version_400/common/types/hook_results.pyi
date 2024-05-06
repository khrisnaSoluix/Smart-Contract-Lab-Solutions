from .account_notification_directive import AccountNotificationDirective as AccountNotificationDirective
from .event_types import ScheduledEvent as ScheduledEvent
from .parameters import OptionalValue as OptionalValue, UnionItemValue as UnionItemValue
from .plan_notification_directive import PlanNotificationDirective as PlanNotificationDirective
from .posting_instructions_directive import PostingInstructionsDirective as PostingInstructionsDirective
from .rejection import Rejection as Rejection
from .update_account_event_type_directive import UpdateAccountEventTypeDirective as UpdateAccountEventTypeDirective
from .update_plan_event_type_directive import UpdatePlanEventTypeDirective as UpdatePlanEventTypeDirective
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

def validate_account_directives(account_directives: Optional[List[AccountNotificationDirective]], posting_directives: Optional[List[PostingInstructionsDirective]], update_events: Optional[List[UpdateAccountEventTypeDirective]]=...):
    ...

def validate_scheduled_events(scheduled_events: Dict[str, ScheduledEvent]):
    ...

def validate_plan_directives(plan_notification_directives: Optional[List[PlanNotificationDirective]]=..., update_events: Optional[List[UpdatePlanEventTypeDirective]]=...):
    ...

def validate_supervisee_directives(supervisee_account_directives: Dict[str, List[AccountNotificationDirective]], supervisee_posting_directives: Dict[str, List[PostingInstructionsDirective]], supervisee_update_account_directives: Dict[str, List[UpdateAccountEventTypeDirective]]):
    ...

class DerivedParameterHookResult:
    parameters_return_value: Dict[str, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]]

    def __init__(self, parameters_return_value: Dict[str, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]]) -> None:
        ...

class DeactivationHookResult:
    account_notification_directives: Optional[List[AccountNotificationDirective]]
    posting_instructions_directives: Optional[List[PostingInstructionsDirective]]
    update_account_event_type_directives: Optional[List[UpdateAccountEventTypeDirective]]
    rejection: Optional[Rejection]

    def __init__(self, *, account_notification_directives: Optional[List[AccountNotificationDirective]]=..., posting_instructions_directives: Optional[List[PostingInstructionsDirective]]=..., update_account_event_type_directives: Optional[List[UpdateAccountEventTypeDirective]]=..., rejection: Optional[Rejection]=...) -> None:
        ...

class ActivationHookResult:
    account_notification_directives: Optional[List[AccountNotificationDirective]]
    posting_instructions_directives: Optional[List[PostingInstructionsDirective]]
    scheduled_events_return_value: Optional[Dict[str, ScheduledEvent]]
    rejection: Optional[Rejection]

    def __init__(self, *, account_notification_directives: Optional[List[AccountNotificationDirective]]=..., posting_instructions_directives: Optional[List[PostingInstructionsDirective]]=..., scheduled_events_return_value: Optional[Dict[str, ScheduledEvent]]=..., rejection: Optional[Rejection]=...) -> None:
        ...

class PostParameterChangeHookResult:
    account_notification_directives: Optional[List[AccountNotificationDirective]]
    posting_instructions_directives: Optional[List[PostingInstructionsDirective]]
    update_account_event_type_directives: Optional[List[UpdateAccountEventTypeDirective]]

    def __init__(self, *, account_notification_directives: Optional[List[AccountNotificationDirective]]=..., posting_instructions_directives: Optional[List[PostingInstructionsDirective]]=..., update_account_event_type_directives: Optional[List[UpdateAccountEventTypeDirective]]=...) -> None:
        ...

class PostPostingHookResult:
    account_notification_directives: Optional[List[AccountNotificationDirective]]
    posting_instructions_directives: Optional[List[PostingInstructionsDirective]]
    update_account_event_type_directives: Optional[List[UpdateAccountEventTypeDirective]]

    def __init__(self, *, account_notification_directives: Optional[List[AccountNotificationDirective]]=..., posting_instructions_directives: Optional[List[PostingInstructionsDirective]]=..., update_account_event_type_directives: Optional[List[UpdateAccountEventTypeDirective]]=..., _from_proto: Optional[bool]=...) -> None:
        ...

class PreParameterChangeHookResult:
    rejection: Optional[Rejection]

    def __init__(self, *, rejection: Optional[Rejection]=...) -> None:
        ...

class PrePostingHookResult:
    rejection: Optional[Rejection]

    def __init__(self, *, rejection: Optional[Rejection]=..., _from_proto: Optional[bool]=...) -> None:
        ...

class ScheduledEventHookResult:
    account_notification_directives: Optional[List[AccountNotificationDirective]]
    posting_instructions_directives: Optional[List[PostingInstructionsDirective]]
    update_account_event_type_directives: Optional[List[UpdateAccountEventTypeDirective]]

    def __init__(self, *, account_notification_directives: Optional[List[AccountNotificationDirective]]=..., posting_instructions_directives: Optional[List[PostingInstructionsDirective]]=..., update_account_event_type_directives: Optional[List[UpdateAccountEventTypeDirective]]=..., _from_proto: Optional[bool]=...) -> None:
        ...

class SupervisorPostPostingHookResult:
    plan_notification_directives: Optional[List[PlanNotificationDirective]]
    update_plan_event_type_directives: Optional[List[UpdatePlanEventTypeDirective]]
    supervisee_account_notification_directives: Optional[Dict[str, List[AccountNotificationDirective]]]
    supervisee_posting_instructions_directives: Optional[Dict[str, List[PostingInstructionsDirective]]]
    supervisee_update_account_event_type_directives: Optional[Dict[str, List[UpdateAccountEventTypeDirective]]]

    def __init__(self, *, plan_notification_directives: Optional[List[PlanNotificationDirective]]=..., update_plan_event_type_directives: Optional[List[UpdatePlanEventTypeDirective]]=..., supervisee_account_notification_directives: Optional[Dict[str, List[AccountNotificationDirective]]]=..., supervisee_posting_instructions_directives: Optional[Dict[str, List[PostingInstructionsDirective]]]=..., supervisee_update_account_event_type_directives: Optional[Dict[str, List[UpdateAccountEventTypeDirective]]]=...) -> None:
        ...

class SupervisorPrePostingHookResult:
    rejection: Optional[Rejection]

    def __init__(self, *, rejection: Optional[Rejection]=...) -> None:
        ...

class SupervisorActivationHookResult:
    scheduled_events_return_value: Optional[Dict[str, ScheduledEvent]]

    def __init__(self, *, scheduled_events_return_value: Optional[Dict[str, ScheduledEvent]]=...) -> None:
        ...

class SupervisorConversionHookResult:
    scheduled_events_return_value: Optional[Dict[str, ScheduledEvent]]

    def __init__(self, *, scheduled_events_return_value: Optional[Dict[str, ScheduledEvent]]=...) -> None:
        ...

class SupervisorScheduledEventHookResult:
    plan_notification_directives: Optional[List[PlanNotificationDirective]]
    update_plan_event_type_directives: Optional[List[UpdatePlanEventTypeDirective]]
    supervisee_account_notification_directives: Optional[Dict[str, List[AccountNotificationDirective]]]
    supervisee_posting_instructions_directives: Optional[Dict[str, List[PostingInstructionsDirective]]]
    supervisee_update_account_event_type_directives: Optional[Dict[str, List[UpdateAccountEventTypeDirective]]]

    def __init__(self, *, plan_notification_directives: Optional[List[PlanNotificationDirective]]=..., update_plan_event_type_directives: Optional[List[UpdatePlanEventTypeDirective]]=..., supervisee_account_notification_directives: Optional[Dict[str, List[AccountNotificationDirective]]]=..., supervisee_posting_instructions_directives: Optional[Dict[str, List[PostingInstructionsDirective]]]=..., supervisee_update_account_event_type_directives: Optional[Dict[str, List[UpdateAccountEventTypeDirective]]]=...) -> None:
        ...

class ConversionHookResult:
    account_notification_directives: Optional[List[AccountNotificationDirective]]
    posting_instructions_directives: Optional[List[PostingInstructionsDirective]]
    scheduled_events_return_value: Optional[Dict[str, ScheduledEvent]]

    def __init__(self, *, account_notification_directives: Optional[List[AccountNotificationDirective]]=..., posting_instructions_directives: Optional[List[PostingInstructionsDirective]]=..., scheduled_events_return_value: Optional[Dict[str, ScheduledEvent]]=...) -> None:
        ...