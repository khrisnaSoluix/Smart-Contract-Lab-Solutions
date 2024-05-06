from unittest import mock

from ..lib import VaultFunctionsABC
from ....version_360.supervisor_contracts.tests.test_lib import (
    PublicSupervisorV360VaultFunctionsTestCase
)


class PublicSupervisorV370VaultFunctionsTestCase(PublicSupervisorV360VaultFunctionsTestCase):
    def test_get_calendar_events(self):

        def foo(vault):
            vault.get_calendar_events(calendar_ids=['foo', 'bar', 'baz'])

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        foo(mock_vault)
