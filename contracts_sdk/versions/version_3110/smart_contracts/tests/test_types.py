from ...common.tests.test_types import PublicCommonV3110TypesTestCase
from ....version_3100.smart_contracts.tests import test_types

from .....utils.tools import SmartContracts3110TestCase


class PublicSmartContractsV3110TypesTestCase(
    SmartContracts3110TestCase,
    PublicCommonV3110TypesTestCase,
    test_types.PublicSmartContractsV3100TypesTestCase,
):
    pass
