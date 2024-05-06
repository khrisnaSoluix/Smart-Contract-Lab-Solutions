from datetime import datetime

from ..types import (
    EndOfMonthSchedule,
    UpdatePlanEventTypeDirective,
    ScheduleSkip,
)
from ...common.tests.test_types import PublicCommonV3110TypesTestCase
from ....version_3100.supervisor_contracts.tests import test_types
from .....utils.exceptions import StrongTypingError, InvalidSmartContractError
from .....utils.tools import SupervisorContracts3110TestCase


class PublicSupervisorContractsV3110TypesTestCase(
    SupervisorContracts3110TestCase,
    PublicCommonV3110TypesTestCase,
    test_types.PublicSupervisorContractsV3100TypesTestCase,
):
    TS_3110 = datetime(year=2020, month=1, day=1)
    plan_id_3110 = "test_plan_id"

    def test_update_plan_event_type_directive(self):
        schedule_method = EndOfMonthSchedule(day=1)
        update_plan_event_type_directive = UpdatePlanEventTypeDirective(
            plan_id=self.plan_id_3110,
            event_type="event_type_1",
            end_datetime=self.TS_3110,
            schedule_method=schedule_method,
            skip=True,
        )
        self.assertEqual(self.plan_id_3110, update_plan_event_type_directive.plan_id)
        self.assertEqual("event_type_1", update_plan_event_type_directive.event_type)
        self.assertEqual(self.TS_3110, update_plan_event_type_directive.end_datetime)
        self.assertEqual(update_plan_event_type_directive.schedule_method, schedule_method)
        self.assertTrue(update_plan_event_type_directive.skip)

    def test_update_plan_event_type_directive_skip_false(self):
        update_plan_event_type_directive = UpdatePlanEventTypeDirective(
            plan_id=self.plan_id_3110,
            event_type="event_type_1",
            end_datetime=self.TS_3110,
            skip=False,
        )
        self.assertEqual(self.plan_id_3110, update_plan_event_type_directive.plan_id)
        self.assertEqual("event_type_1", update_plan_event_type_directive.event_type)
        self.assertEqual(self.TS_3110, update_plan_event_type_directive.end_datetime)
        self.assertFalse(update_plan_event_type_directive.skip)

    def test_update_plan_event_type_directive_schedule_skip(self):
        skip_end = datetime(year=2021, month=1, day=1)
        update_plan_event_type_directive = UpdatePlanEventTypeDirective(
            plan_id=self.plan_id_3110,
            event_type="event_type_1",
            end_datetime=self.TS_3110,
            skip=ScheduleSkip(end=skip_end),
        )
        self.assertEqual(self.plan_id_3110, update_plan_event_type_directive.plan_id)
        self.assertEqual("event_type_1", update_plan_event_type_directive.event_type)
        self.assertEqual(self.TS_3110, update_plan_event_type_directive.end_datetime)
        self.assertIsNotNone(update_plan_event_type_directive.skip)
        self.assertEqual(skip_end, update_plan_event_type_directive.skip.end)

    def test_update_plan_event_type_directive_skip_attribute_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            UpdatePlanEventTypeDirective(
                plan_id=self.plan_id_3110,
                event_type="event_type_1",
                end_datetime=self.TS_3110,
                skip="not_valid",
            )
        self.assertIn(
            "'skip' expected Optional[Union[bool, ScheduleSkip]] but got value 'not_valid'",
            str(ex.exception),
        )

    def test_update_plan_event_type_directive_no_end_datetime_or_schedule(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdatePlanEventTypeDirective(
                plan_id=self.plan_id_3110,
                event_type="event_type_1",
            )

        self.assertIn(
            ("UpdatePlanEventTypeDirective object has to have either an end_datetime, a "),
            str(ex.exception),
        )

    def test_update_plan_event_type_directive_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            UpdatePlanEventTypeDirective(
                plan_id=123,
                event_type="event_type_1",
                end_datetime=self.TS_3110,
            )

        self.assertIn("'plan_id' expected str but got value 123", str(ex.exception))
