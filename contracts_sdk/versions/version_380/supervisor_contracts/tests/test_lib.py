from unittest import mock

from ..lib import VaultFunctionsABC
from ....version_370.supervisor_contracts.tests.test_lib import (
    PublicSupervisorV370VaultFunctionsTestCase
)


class PublicSupervisorV380VaultFunctionsTestCase(PublicSupervisorV370VaultFunctionsTestCase):
    def test_update_event_type(self):

        def foo(vault):
            vault.update_event_type(event_type='foo')

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        foo(mock_vault)
