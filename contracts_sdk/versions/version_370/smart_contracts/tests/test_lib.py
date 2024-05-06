from ....version_360.smart_contracts.tests.test_lib import PublicV360VaultFunctionsTestCase
from .....utils.tools import SmartContracts370TestCase


class PublicV370VaultFunctionsTestCase(
        SmartContracts370TestCase,
        PublicV360VaultFunctionsTestCase
):

    def test_get_calendar_events(self):

        def foo(vault):
            vault.get_calendar_events(calendar_ids=['foo', 'bar', 'baz'])

        foo(self.vault)

    def test_make_internal_transfer_instructions(self):

        def foo(vault):
            vault.make_internal_transfer_instructions(
                amount=10,
                denomination='GBP',
                client_transaction_id='1234',
                from_account_id='4444444',
                to_account_id='2222222',
                transaction_code='ABC123'
            )

        foo(self.vault)
