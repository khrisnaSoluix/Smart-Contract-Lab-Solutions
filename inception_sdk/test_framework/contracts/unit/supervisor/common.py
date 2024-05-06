# standard libs
from datetime import datetime
from unittest.mock import Mock

# contracts api
from contracts_api import (
    CalendarEvent,
    CalendarEvents,
    PostPostingHookResult,
    PrePostingHookResult,
    ScheduledEventHookResult,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.common import (
    DEFAULT_DATETIME,
    DEFAULT_HOOK_EXECUTION_ID,
    ContractTest,
)

DEFAULT_PLAN_ID = "MOCK_PLAN"


class SupervisorContractTest(ContractTest):
    def create_supervisee_mock(
        self,
        supervisee_alias: str | None = None,
        supervisee_hook_result: (
            PostPostingHookResult | PrePostingHookResult | ScheduledEventHookResult | None
        ) = None,
        **kwargs
    ) -> Mock:
        """_summary_
        # supervisee specific arguments - these following arguments should only used on supervisee
        vault objects
        :param requires_fetched_balances: balances fetched from the requires decorator, this should
        only be used in the post_posting_hook or scheduled_event_hook where optimised data fetchers
        for supervisors are not yet supported
        :param requires_fetched_client_transactions: client transactions fetched from the requires
        decorator, this should only be used in the post_posting_hook or scheduled_event_hook where
        optimised data fetchers for supervisors are not yet supported
        :param requires_fetched_postings: postings fetched from the requires decorator, this should
        only be used in the post_posting_hook or scheduled_event_hook where optimised data fetchers
        for supervisors are not yet supported
        :param supervisee_alias: alias of the supervisee vault object
        :param supervisee_hook_result: returned hook result of the supervised hook
        :param is_supervisee_vault: boolean used to determine whether this is a supervisee vault
        object or not
        """
        if "is_supervisee_vault" not in kwargs:
            kwargs["is_supervisee_vault"] = True
        return super().create_mock(
            supervisee_alias=supervisee_alias,
            supervisee_hook_result=supervisee_hook_result,
            **kwargs
        )

    def create_supervisor_mock(
        self,
        supervisees: dict[str, Mock] | None = None,
        creation_date: datetime = DEFAULT_DATETIME,
        calendar_events: list[CalendarEvent] | None = None,
        plan_id: str = DEFAULT_PLAN_ID,
        existing_mock: Mock | None = None,
    ) -> Mock:
        """
        Create mock Vault object for supervisor using base unit test create_mock.
        """
        supervisees = supervisees or {}

        calendar_events = [
            CalendarEvent(
                id=calendar_event.id,
                calendar_id=calendar_event.calendar_id.replace("&{", "").replace("}", ""),
                start_datetime=calendar_event.start_datetime,
                end_datetime=calendar_event.end_datetime,
            )
            for calendar_event in calendar_events or []
        ]

        def mock_get_calendar_events(calendar_ids: list[str]) -> CalendarEvents | None:
            # replace CLU dependency syntax from flag definitions. This allows for consistency
            # between the contract and the tests since unit tests run the contract directly as
            # a python module, these aren't removed in any class setup or rendering
            calendar_ids = [
                calendar_id.replace("&{", "").replace("}", "") for calendar_id in calendar_ids
            ]
            events = [event for event in calendar_events if event.calendar_id in calendar_ids]
            return CalendarEvents(calendar_events=events) if events else None

        mock_supervisor_vault = existing_mock or Mock()

        # attributes
        mock_supervisor_vault.plan_id = plan_id
        mock_supervisor_vault.supervisees = supervisees

        # supervisor vault methods
        mock_supervisor_vault.get_plan_opening_datetime.return_value = creation_date
        mock_supervisor_vault.get_hook_execution_id.return_value = DEFAULT_HOOK_EXECUTION_ID
        mock_supervisor_vault.get_calendar_events.side_effect = mock_get_calendar_events

        return mock_supervisor_vault


class SupervisorFeatureTest(SupervisorContractTest):
    # Override tside since features should not need them, but if a specific test needs tside
    # then this can be set at the class level
    tside = None  # type: ignore
