from ...common.tests.test_types import PublicCommonV3120TypesTestCase
from ....version_3110.smart_contracts.tests import test_types

from .....utils.tools import SmartContracts3120TestCase


class PublicSmartContractsV3110TypesTestCase(
    SmartContracts3120TestCase,
    PublicCommonV3120TypesTestCase,
    test_types.PublicSmartContractsV3110TypesTestCase,
):
    pass
