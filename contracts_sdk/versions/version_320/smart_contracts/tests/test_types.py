from ...common.tests.test_types import PublicCommonV320TypesTestCase
from ....version_310.smart_contracts.tests import test_types
from .....utils.tools import SmartContracts320TestCase


class PublicSmartContractsV320TypesTestCase(
    SmartContracts320TestCase,
    PublicCommonV320TypesTestCase,
    test_types.PublicSmartContractsV310TypesTestCase
):
    pass
