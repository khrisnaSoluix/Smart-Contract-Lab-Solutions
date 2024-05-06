from ..types import SmartContractDescriptor, EventType
from ...common.tests.test_types import PublicCommonV340TypesTestCase
from .....utils.exceptions import StrongTypingError
from .....utils.tools import SupervisorContracts340TestCase


class PublicSupervisorContractsV340TypesTestCase(
    SupervisorContracts340TestCase,
    PublicCommonV340TypesTestCase
):
    def test_event_type_object(self):
        event_type_name = 'TEST_EVENT_1'
        scheduler_tag_ids = ['TEST_TAG_1', 'TEST_TAG_2']
        overrides_event_types = [
            ('S1', 'TEST_EVENT_2'),
            ('S2', 'TEST_EVENT_3'),
        ]

        event_type = EventType(
            name=event_type_name,
            scheduler_tag_ids=scheduler_tag_ids,
            overrides_event_types=overrides_event_types,
        )

        self.assertEqual(event_type_name, event_type.name)
        self.assertEqual(scheduler_tag_ids, event_type.scheduler_tag_ids)
        self.assertEqual(overrides_event_types, event_type.overrides_event_types)

    def test_event_type_attributes_are_verified(self):
        illegal_overrides_event_types_value = [{'key': 'value'}]
        with self.assertRaises(StrongTypingError) as ex:
            EventType(
                name='TEST_EVENT_1',
                scheduler_tag_ids=['TEST_TAG_1', 'TEST_TAG_2'],
                overrides_event_types=illegal_overrides_event_types_value,
            )
        self.assertIn(
            f"overrides_event_types\' expected Optional[List[Tuple[str, str]]] but got value "
            f'{illegal_overrides_event_types_value}',
            str(ex.exception)
        )

    def test_smart_contract_descriptor(self):
        supervised_smart_contract = SmartContractDescriptor(
            alias='test1',
            smart_contract_version_id='test_smart_contract_version_id'
        )
        self.assertEqual('test1', supervised_smart_contract.alias)

    def test_smart_contract_descriptor_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            SmartContractDescriptor(
                alias=None,
                smart_contract_version_id='test_smart_contract_version_id'
            )
        self.assertIn(
            "\'alias\' expected str but got value None",
            str(ex.exception)
        )
