from ..types import EventType
from ...common.tests.test_types import PublicCommonV330TypesTestCase
from ....version_320.smart_contracts.tests import test_types
from .....utils.tools import SmartContracts330TestCase
from .....utils.exceptions import StrongTypingError


class PublicSmartContractsV330TypesTestCase(
    SmartContracts330TestCase,
    PublicCommonV330TypesTestCase,
    test_types.PublicSmartContractsV320TypesTestCase
):

    def test_event_type_can_be_created(self):
        event_type = EventType(
            name='name',
            scheduler_tag_ids=['TAG']
        )
        self.assertEqual(event_type.name, 'name')
        self.assertEqual(event_type.scheduler_tag_ids, ['TAG'])

    def test_event_types_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            EventType(
                name=None,
                scheduler_tag_ids=['TAG']
            )
        self.assertIn(
            '\'name\' expected str but got value None',
            str(ex.exception)
        )
