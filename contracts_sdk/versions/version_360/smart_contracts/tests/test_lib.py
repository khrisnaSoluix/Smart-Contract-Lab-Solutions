from ....version_350.smart_contracts.tests.test_lib import PublicV350VaultFunctionsTestCase
from .....utils.tools import SmartContracts360TestCase


class PublicV360VaultFunctionsTestCase(
        SmartContracts360TestCase,
        PublicV350VaultFunctionsTestCase
):
    pass
