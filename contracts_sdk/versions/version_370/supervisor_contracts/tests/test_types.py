from ..types import SmartContractDescriptor
from ...common.tests.test_types import PublicCommonV370TypesTestCase
from ....version_360.supervisor_contracts.tests import test_types
from .....utils.tools import SupervisorContracts370TestCase
from .....utils.exceptions import StrongTypingError


class PublicSupervisorContractsV370TypesTestCase(
    SupervisorContracts370TestCase,
    PublicCommonV370TypesTestCase,
    test_types.PublicSupervisorContractsV360TypesTestCase
):
    def test_smart_contract_descriptor(self):
        supervised_smart_contract = SmartContractDescriptor(
            alias='test1',
            smart_contract_version_id='test_smart_contract_version_id',
            supervise_post_posting_hook=True,
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
