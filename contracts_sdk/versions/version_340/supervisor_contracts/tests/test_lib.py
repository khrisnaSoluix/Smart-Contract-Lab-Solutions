from datetime import datetime
from unittest import mock, TestCase

from ..lib import VaultFunctionsABC


class PublicSupervisorV340VaultFunctionsTestCase(TestCase):
    def test_create_mock_vault(self):

        def foo(vault):
            return vault.get_hook_execution_id()

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        mock_vault.get_hook_execution_id.return_value = '1234'
        response = foo(mock_vault)
        mock_vault.get_hook_execution_id.assert_called_once()
        self.assertEqual('1234', response)

    def test_cannot_use_unknown_vault_method(self):

        def foo(vault):
            vault.some_unknown_method()

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        with self.assertRaises(AttributeError):
            foo(mock_vault)

    def test_cannot_mock_return_value_on_unknown_method(self):
        mock_vault = mock.create_autospec(VaultFunctionsABC)
        with self.assertRaises(AttributeError):
            mock_vault.some_unknown_method.return_value = 1

    def test_mock_vault_raises_error_on_unexpected_args(self):

        def foo(vault):
            vault.get_last_execution_time(event_type='1234', unexpected_arg='boo')

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        with self.assertRaises(TypeError):
            foo(mock_vault)

        mock_vault.get_last_execution_time.return_value = 'some time'
        with self.assertRaises(TypeError):
            foo(mock_vault)

    def test_mock_vault_raises_error_on_missing_args(self):

        def foo(vault):
            vault.get_last_execution_time()

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        with self.assertRaises(TypeError):
            foo(mock_vault)

        mock_vault.get_last_execution_time.return_value = 'some time'
        with self.assertRaises(TypeError):
            foo(mock_vault)

    def test_get_last_execution_time(self):

        def foo(vault):
            vault.get_last_execution_time(event_type='foo')

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        foo(mock_vault)

    def test_localize_datetime(self):

        def foo(vault):
            vault.localize_datetime(dt=datetime.utcnow())

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        foo(mock_vault)

    def test_get_plan_creation_date(self):

        def foo(vault):
            vault.get_plan_creation_date()

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        foo(mock_vault)

    def test_get_hook_execution_id(self):

        def foo(vault):
            vault.get_hook_execution_id()

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        foo(mock_vault)
