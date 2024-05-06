from ....version_380.smart_contracts.tests.test_lib import PublicV380VaultFunctionsTestCase
from .....utils.tools import SmartContracts390TestCase


class PublicV390VaultFunctionsTestCase(
        SmartContracts390TestCase,
        PublicV380VaultFunctionsTestCase
):
    pass
