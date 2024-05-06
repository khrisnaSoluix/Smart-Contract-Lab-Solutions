from ....version_300.smart_contracts.tests.test_lib import PublicV300VaultFunctionsTestCase
from .....utils.tools import SmartContracts310TestCase


class PublicV310VaultFunctionsTestCase(
        SmartContracts310TestCase,
        PublicV300VaultFunctionsTestCase
):

    def test_make_internal_transfer_instructions(self):

        def foo(vault):
            vault.make_internal_transfer_instructions(
                amount=10,
                denomination='GBP',
                client_transaction_id='1234',
                from_account_id='4444444',
                to_account_id='2222222',
                override_all_restrictions=True
            )

        foo(self.vault)
