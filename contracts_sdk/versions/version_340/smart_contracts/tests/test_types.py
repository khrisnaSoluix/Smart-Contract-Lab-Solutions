from ...common.tests.test_types import PublicCommonV340TypesTestCase
from ....version_330.smart_contracts.tests import test_types
from .....utils.tools import SmartContracts340TestCase


class PublicSmartContractsV340TypesTestCase(
    SmartContracts340TestCase,
    PublicCommonV340TypesTestCase,
    test_types.PublicSmartContractsV330TypesTestCase
):
    pass
