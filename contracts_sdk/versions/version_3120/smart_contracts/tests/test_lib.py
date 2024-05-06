from ....version_3110.smart_contracts.tests.test_lib import PublicV3110VaultFunctionsTestCase
from .....utils.tools import SmartContracts3120TestCase


class PublicV3120VaultFunctionsTestCase(
    SmartContracts3120TestCase, PublicV3110VaultFunctionsTestCase
):
    def test_instruct_notification(self):
        def foo(vault):
            vault.instruct_notification(
                notification_type="foo", notification_details={"foo": "bar"}
            )

        foo(self.vault)
