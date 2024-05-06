from datetime import datetime

from ....version_320.smart_contracts.tests.test_lib import PublicV320VaultFunctionsTestCase
from .....utils.tools import SmartContracts330TestCase


class PublicV330VaultFunctionsTestCase(
        SmartContracts330TestCase,
        PublicV320VaultFunctionsTestCase
):

    def test_localize_datetime(self):

        def foo(vault):
            vault.localize_datetime(dt=datetime.utcnow())

        foo(self.vault)

    def test_amend_schedule(self):

        def foo(vault):
            vault.amend_schedule(event_type='foo', new_schedule='bar')

        foo(self.vault)

    def test_remove_schedule(self):

        def foo(vault):
            vault.remove_schedule(event_type='foo')

        foo(self.vault)
