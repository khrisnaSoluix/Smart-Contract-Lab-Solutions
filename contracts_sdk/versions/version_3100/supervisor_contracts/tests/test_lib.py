from unittest import mock

from ..lib import VaultFunctionsABC
from ....version_390.supervisor_contracts.tests.test_lib import (
    PublicSupervisorV390VaultFunctionsTestCase
)


class PublicSupervisorV3100VaultFunctionsTestCase(PublicSupervisorV390VaultFunctionsTestCase):

    def test_get_scheduled_job_details(self):

        def foo(vault):
            vault.get_scheduled_job_details()

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        foo(mock_vault)
