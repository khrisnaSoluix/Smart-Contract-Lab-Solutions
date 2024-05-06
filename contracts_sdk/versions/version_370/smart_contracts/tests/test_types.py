from ...common.tests.test_types import PublicCommonV370TypesTestCase
from ....version_360.smart_contracts.tests import test_types
from .....utils.tools import SmartContracts370TestCase


class PublicSmartContractsV370TypesTestCase(
    SmartContracts370TestCase,
    PublicCommonV370TypesTestCase,
    test_types.PublicSmartContractsV360TypesTestCase
):
    pass
