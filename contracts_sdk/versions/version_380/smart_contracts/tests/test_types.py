from ...common.tests.test_types import PublicCommonV380TypesTestCase
from ....version_370.smart_contracts.tests import test_types
from .....utils.tools import SmartContracts380TestCase


class PublicSmartContractsV380TypesTestCase(
    SmartContracts380TestCase,
    PublicCommonV380TypesTestCase,
    test_types.PublicSmartContractsV370TypesTestCase
):
    pass
