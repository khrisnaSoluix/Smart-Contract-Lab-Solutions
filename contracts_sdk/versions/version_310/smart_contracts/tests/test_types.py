from ...common.tests.test_types import PublicCommonV310TypesTestCase
from ....version_300.smart_contracts.tests import test_types
from .....utils.tools import SmartContracts310TestCase


class PublicSmartContractsV310TypesTestCase(
    SmartContracts310TestCase,
    PublicCommonV310TypesTestCase,
    test_types.PublicSmartContractsV300TypesTestCase
):
    pass
