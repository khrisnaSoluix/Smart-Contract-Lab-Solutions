from ...common.tests.test_types import PublicCommonV360TypesTestCase
from ....version_350.smart_contracts.tests import test_types
from .....utils.tools import SmartContracts360TestCase


class PublicSmartContractsV360TypesTestCase(
    SmartContracts360TestCase,
    PublicCommonV360TypesTestCase,
    test_types.PublicSmartContractsV350TypesTestCase
):
    pass
