from unittest import mock, TestCase

from .. import lib as smart_contracts_lib


class PublicV400VaultFunctionsTestCase(TestCase):
    def setUp(self, *args, **kwargs):
        self.vault = mock.create_autospec(smart_contracts_lib.VaultFunctionsABC)

    def test_cannot_use_unknown_vault_method(self):
        def foo(vault):
            vault.some_unknown_method()

        with self.assertRaises(AttributeError):
            foo(self.vault)

    def test_cannot_mock_return_value_on_unknown_method(self):
        with self.assertRaises(AttributeError):
            self.vault.some_unknown_method.return_value = 1

    def test_mock_vault_raises_error_on_unexpected_args(self):
        def foo(vault):
            vault.get_last_execution_datetime(event_type="1234", unexpected_arg="boo")

        with self.assertRaises(TypeError):
            foo(self.vault)

        self.vault.get_last_execution_datetime.return_value = "some schedule"
        with self.assertRaises(TypeError):
            foo(self.vault)

    def test_mock_vault_raises_error_on_missing_args(self):
        def foo(vault):
            vault.get_last_execution_datetime()

        with self.assertRaises(TypeError):
            foo(self.vault)

        self.vault.get_last_execution_datetime.return_value = "some schedule"
        with self.assertRaises(TypeError):
            foo(self.vault)

    def test_get_last_execution_datetime(self):
        def foo(vault):
            vault.get_last_execution_datetime(event_type="foo")

        foo(self.vault)

    def test_get_posting_instructions(self):
        def foo(vault):
            vault.get_posting_instructions()

        foo(self.vault)

    def test_get_client_transactions(self):
        def foo(vault):
            vault.get_client_transactions()

        foo(self.vault)

    def test_get_account_creation_datetime(self):
        def foo(vault):
            vault.get_account_creation_datetime()

        foo(self.vault)

    def test_get_balances_timeseries(self):
        def foo(vault):
            vault.get_balances_timeseries()

        foo(self.vault)

    def test_get_hook_execution_id(self):
        def foo(vault):
            return vault.get_hook_execution_id()

        self.vault.get_hook_execution_id.return_value = "2127"
        hook_execution_id = foo(self.vault)
        self.vault.get_hook_execution_id.assert_called_once()
        self.assertEqual("2127", hook_execution_id)

    def test_get_parameter_timeseries(self):
        def foo(vault):
            vault.get_parameter_timeseries(name="foo")

        foo(self.vault)

    def test_get_flag_timeseries(self):
        def foo(vault):
            vault.get_flag_timeseries(flag="foo")

        foo(self.vault)

    def test_mock_vault_response_does_not_leak_flag_timeseries(self):
        def foo(vault):
            return vault.get_parameter_timeseries(name="foo")

        self.vault.get_flag_timeseries.return_value = "other flags"
        response = foo(self.vault)
        self.assertNotEqual("other parameters", response)
        self.vault.get_parameter_timeseries.assert_called_once()
        self.vault.get_flag_timeseries.assert_not_called()

    def test_mock_vault_response_does_not_leak_parameter_timeseries(self):
        def foo(vault):
            return vault.get_flag_timeseries(flag="foo")

        self.vault.get_parameter_timeseries.return_value = "other parameters"
        response = foo(self.vault)
        self.assertNotEqual("other flags", response)
        self.vault.get_flag_timeseries.assert_called_once()
        self.vault.get_parameter_timeseries.assert_not_called()

    def test_get_hook_result(self):
        def foo(vault):
            vault.get_hook_result()

        foo(self.vault)

    def test_get_alias(self):
        def foo(vault):
            vault.get_alias()

        foo(self.vault)

    def test_get_permitted_denominations(self):
        def foo(vault):
            vault.get_permitted_denominations()

        foo(self.vault)

    def test_get_calendar_events(self):
        def foo(vault):
            vault.get_calendar_events(calendar_ids=["foo", "bar", "baz"])

        foo(self.vault)
