from ..types import EventTypesGroup
from ....version_320.common.tests.test_types import PublicCommonV320TypesTestCase
from .....utils.exceptions import InvalidSmartContractError, StrongTypingError


class PublicCommonV330TypesTestCase(PublicCommonV320TypesTestCase):

    def test_event_types_group_can_be_created(self):
        event_types_group = EventTypesGroup(
            name='TestEvenTypesGroup',
            event_types_order=['EVENT_TYPE1', 'EVENT_TYPE2']
        )
        self.assertEqual(event_types_group.name, 'TestEvenTypesGroup')
        self.assertEqual(event_types_group.event_types_order, ['EVENT_TYPE1', 'EVENT_TYPE2'])

    def test_event_types_group_not_enough_event_types(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            EventTypesGroup(
                name='TestEvenTypesGroup',
                event_types_order=['EVENT_TYPE']
            )
        self.assertIn(
            'An EventTypesGroup must have at least two event types',
            str(ex.exception)
        )

    def test_event_types_group_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            EventTypesGroup(
                name='TestEvenTypesGroup',
                event_types_order=None
            )
        self.assertIn(
            "'event_types_order' expected List[str] but got value None",
            str(ex.exception)
        )
