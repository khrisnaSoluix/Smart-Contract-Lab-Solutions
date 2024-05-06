from ....version_370.smart_contracts.tests.test_lib import PublicV370VaultFunctionsTestCase
from .....utils.tools import SmartContracts380TestCase


class PublicV380VaultFunctionsTestCase(
        SmartContracts380TestCase,
        PublicV370VaultFunctionsTestCase
):

    def test_update_event_type(self):

        def foo(vault):
            vault.update_event_type(event_type='foo')

        foo(self.vault)

    def test_amend_schedule(self):

        def foo(vault):
            vault.amend_schedule(event_type='foo', new_schedule='bar')

        foo(self.vault)

    def test_remove_schedule(self):

        def foo(vault):
            vault.remove_schedule(event_type='foo')

        foo(self.vault)
