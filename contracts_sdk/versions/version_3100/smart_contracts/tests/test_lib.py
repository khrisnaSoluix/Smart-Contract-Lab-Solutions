from ....version_390.smart_contracts.tests.test_lib import PublicV390VaultFunctionsTestCase
from .....utils.tools import SmartContracts3100TestCase


class PublicV3100VaultFunctionsTestCase(
        SmartContracts3100TestCase,
        PublicV390VaultFunctionsTestCase
):

    def test_get_scheduled_job_details(self):

        def foo(vault):
            vault.get_scheduled_job_details()

        foo(self.vault)
