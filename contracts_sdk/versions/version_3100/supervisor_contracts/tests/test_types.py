from datetime import datetime

from ..types import (
    UpdatePlanEventTypeDirective,
    EventTypeSchedule,
    EndOfMonthSchedule,
)
from ...common.tests.test_types import PublicCommonV3100TypesTestCase
from ....version_390.supervisor_contracts.tests import test_types
from .....utils.tools import SupervisorContracts3100TestCase
from .....utils.exceptions import StrongTypingError, InvalidSmartContractError


class PublicSupervisorContractsV3100TypesTestCase(
    SupervisorContracts3100TestCase,
    PublicCommonV3100TypesTestCase,
    test_types.PublicSupervisorContractsV390TypesTestCase,
):
    TS_3100 = datetime(year=2020, month=1, day=1)
    plan_id_3100 = "test_plan_id"

    def test_update_plan_event_type_directive(self):
        schedule_method = EndOfMonthSchedule(day=1)
        update_plan_event_type_directive = UpdatePlanEventTypeDirective(
            plan_id=self.plan_id_3100,
            event_type="event_type_1",
            end_datetime=self.TS_3100,
            schedule_method=schedule_method,
        )
        self.assertEqual(update_plan_event_type_directive.plan_id, self.plan_id_3100)
        self.assertEqual(update_plan_event_type_directive.event_type, "event_type_1")
        self.assertEqual(update_plan_event_type_directive.end_datetime, self.TS_3100)
        self.assertEqual(update_plan_event_type_directive.schedule_method, schedule_method)

    def test_update_plan_event_type_directive_no_end_datetime_or_schedule(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdatePlanEventTypeDirective(
                plan_id=self.plan_id_3100,
                event_type="event_type_1",
            )

        self.assertIn(
            (
                "UpdatePlanEventTypeDirective object has to have either an end_datetime, a "
                "schedule or schedule_method defined"
            ),
            str(ex.exception),
        )

    def test_update_plan_event_type_directive_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            UpdatePlanEventTypeDirective(
                plan_id=123,
                event_type="event_type_1",
                end_datetime=self.TS_3100,
            )

        self.assertIn("'plan_id' expected str but got value 123", str(ex.exception))

    def test_update_plan_event_type_directive_validation(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdatePlanEventTypeDirective(
                plan_id=self.plan_id_3100,
                event_type="event_type_1",
                schedule_method=EndOfMonthSchedule(day=1),
                schedule=EventTypeSchedule(day="1"),
            )
        self.assertEqual(
            "UpdatePlanEventTypeDirective cannot contain both"
            " schedule and schedule_method fields",
            str(ex.exception),
        )
