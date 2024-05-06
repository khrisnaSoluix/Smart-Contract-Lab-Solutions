from ....version_330.smart_contracts.tests.test_lib import PublicV330VaultFunctionsTestCase
from .....utils.tools import SmartContracts340TestCase


class PublicV340VaultFunctionsTestCase(
        SmartContracts340TestCase,
        PublicV330VaultFunctionsTestCase
):

    def test_get_hook_directives(self):

        def foo(vault):
            vault.get_hook_directives()

        foo(self.vault)

    def test_get_alias(self):

        def foo(vault):
            vault.get_alias()

        foo(self.vault)

    def test_get_flag_timeseries(self):

        def foo(vault):
            vault.get_flag_timeseries(flag='SOME_FLAG')

        foo(self.vault)
