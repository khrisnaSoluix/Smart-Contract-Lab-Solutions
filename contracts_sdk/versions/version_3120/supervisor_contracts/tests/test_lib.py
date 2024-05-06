from unittest import mock

from ..lib import VaultFunctionsABC
from ....version_3110.supervisor_contracts.tests.test_lib import (
    PublicSupervisorV3110VaultFunctionsTestCase,
)


class PublicSupervisorV3120VaultFunctionsTestCase(PublicSupervisorV3110VaultFunctionsTestCase):
    def test_instruct_notification(self):
        def foo(vault):
            vault.instruct_notification(
                notification_type="foo", notification_details={"foo": "bar"}
            )

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        foo(mock_vault)
