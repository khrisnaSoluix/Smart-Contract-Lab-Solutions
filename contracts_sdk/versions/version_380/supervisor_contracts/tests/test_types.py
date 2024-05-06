from datetime import datetime

from ..types import UpdatePlanEventTypeDirective
from ...common.tests.test_types import PublicCommonV380TypesTestCase
from ....version_370.supervisor_contracts.tests import test_types
from .....utils.tools import SupervisorContracts380TestCase

from .....utils.exceptions import InvalidSmartContractError, StrongTypingError


class PublicSupervisorContractsV380TypesTestCase(
    SupervisorContracts380TestCase,
    PublicCommonV380TypesTestCase,
    test_types.PublicSupervisorContractsV370TypesTestCase,
):
    TS_380 = datetime(year=2020, month=1, day=1)
    plan_id_380 = "test_plan_id"

    def test_update_plan_event_type_directive(self):
        update_plan_event_type_directive = UpdatePlanEventTypeDirective(
            plan_id=self.plan_id_380,
            event_type="event_type_1",
            end_datetime=self.TS_380,
        )
        self.assertEqual(update_plan_event_type_directive.plan_id, self.plan_id_380)
        self.assertEqual(update_plan_event_type_directive.event_type, "event_type_1")
        self.assertEqual(update_plan_event_type_directive.end_datetime, self.TS_380)

    def test_update_plan_event_type_directive_no_end_datetime_or_schedule(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdatePlanEventTypeDirective(
                plan_id=self.plan_id_380,
                event_type="event_type_1",
            )

        self.assertIn(
            (
                "UpdatePlanEventTypeDirective object has to have either an end_datetime or a "
                "schedule defined"
            ),
            str(ex.exception),
        )

    def test_update_plan_event_type_directive_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            UpdatePlanEventTypeDirective(
                plan_id=123,
                event_type="event_type_1",
                end_datetime=self.TS_380,
            )

        self.assertIn("'plan_id' expected str but got value 123", str(ex.exception))
