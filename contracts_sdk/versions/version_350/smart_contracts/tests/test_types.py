from ...common.tests.test_types import PublicCommonV350TypesTestCase
from ....version_340.smart_contracts.tests import test_types
from .....utils.tools import SmartContracts350TestCase


class PublicSmartContractsV350TypesTestCase(
    SmartContracts350TestCase,
    PublicCommonV350TypesTestCase,
    test_types.PublicSmartContractsV340TypesTestCase
):
    pass
