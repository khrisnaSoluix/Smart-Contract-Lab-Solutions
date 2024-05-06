from unittest import mock, TestCase

from ..lib import VaultFunctionsABC


class PublicSupervisorV400VaultFunctionsTestCase(TestCase):
    def test_create_mock_vault(self):
        def foo(vault):
            return vault.get_hook_execution_id()

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        mock_vault.get_hook_execution_id.return_value = "1234"
        response = foo(mock_vault)
        mock_vault.get_hook_execution_id.assert_called_once()
        self.assertEqual("1234", response)

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

    def test_get_plan_opening_datetime(self):
        def foo(vault):
            vault.get_plan_opening_datetime()

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        foo(mock_vault)

    def test_get_hook_execution_id(self):
        def foo(vault):
            vault.get_hook_execution_id()

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        foo(mock_vault)

    def test_get_calendar_events(self):
        def foo(vault):
            vault.get_calendar_events(calendar_ids=["foo", "bar", "baz"])

        mock_vault = mock.create_autospec(VaultFunctionsABC)
        foo(mock_vault)
