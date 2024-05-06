from ..types import (
    SmartContractDescriptor,
    SupervisedHooks,
    SupervisionExecutionMode,
)
from ...common.tests.test_types import PublicCommonV3120TypesTestCase
from ....version_3110.supervisor_contracts.tests import test_types
from .....utils.exceptions import StrongTypingError
from .....utils.tools import SupervisorContracts3120TestCase
from .....utils.feature_flags import (
    skip_if_not_enabled,
    PRE_POSTING_SUPERVISION,
)


class PublicSupervisorContractsV3120TypesTestCase(
    SupervisorContracts3120TestCase,
    PublicCommonV3120TypesTestCase,
    test_types.PublicSupervisorContractsV3110TypesTestCase,
):
    @skip_if_not_enabled(feature_flag=PRE_POSTING_SUPERVISION)
    def test_smart_contract_descriptor_no_supervised_hooks(self):
        supervised_smart_contract = SmartContractDescriptor(
            alias="test1", smart_contract_version_id="test_smart_contract_version_id"
        )
        self.assertEqual("test1", supervised_smart_contract.alias)
        self.assertIsNone(supervised_smart_contract.supervised_hooks)

    @skip_if_not_enabled(feature_flag=PRE_POSTING_SUPERVISION)
    def test_smart_contract_descriptor_with_supervised_hooks_wrong_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            SmartContractDescriptor(
                alias="test1",
                smart_contract_version_id="test_smart_contract_version_id",
                supervised_hooks=1,
            )
        self.assertEqual(
            "SmartContractDescriptor.__init__ arg 'supervised_hooks'"
            " expected Optional[SupervisedHooks] but got value 1",
            str(ex.exception),
        )

    @skip_if_not_enabled(feature_flag=PRE_POSTING_SUPERVISION)
    def test_smart_contract_descriptor_supervised_hooks(self):
        supervised_hooks = SupervisedHooks(pre_posting_code=SupervisionExecutionMode.OVERRIDE)
        supervised_smart_contract = SmartContractDescriptor(
            alias="test1",
            smart_contract_version_id="test_smart_contract_version_id",
            supervised_hooks=supervised_hooks,
        )
        self.assertEqual("test1", supervised_smart_contract.alias)
        self.assertEqual(supervised_hooks, supervised_smart_contract.supervised_hooks)

    @skip_if_not_enabled(feature_flag=PRE_POSTING_SUPERVISION)
    def test_smart_contract_descriptor(self):
        supervised_smart_contract = SmartContractDescriptor(
            alias="test1",
            smart_contract_version_id="test_smart_contract_version_id",
            supervise_post_posting_hook=True,
        )
        self.assertEqual("test1", supervised_smart_contract.alias)

    @skip_if_not_enabled(feature_flag=PRE_POSTING_SUPERVISION)
    def test_smart_contract_descriptor_attributes_are_verified(self):
        with self.assertRaises(StrongTypingError) as ex:
            SmartContractDescriptor(
                alias=None, smart_contract_version_id="test_smart_contract_version_id"
            )
        self.assertIn("'alias' expected str but got value None", str(ex.exception))
