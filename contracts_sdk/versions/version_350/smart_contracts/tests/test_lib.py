from ....version_340.smart_contracts.tests.test_lib import PublicV340VaultFunctionsTestCase
from .....utils.tools import SmartContracts350TestCase


class PublicV350VaultFunctionsTestCase(
        SmartContracts350TestCase,
        PublicV340VaultFunctionsTestCase
):

    def test_get_permitted_denominations(self):

        def foo(vault):
            vault.get_permitted_denominations()

        foo(self.vault)
