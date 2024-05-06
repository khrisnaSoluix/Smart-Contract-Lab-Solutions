from .....utils.tools import SmartContracts300TestCase


class PublicV300VaultFunctionsTestCase(SmartContracts300TestCase):

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
            vault.remove_schedule(event_type='1234', unexpected_arg='boo')

        with self.assertRaises(TypeError):
            foo(self.vault)

        self.vault.remove_schedule.return_value = 'some schedule'
        with self.assertRaises(TypeError):
            foo(self.vault)

    def test_mock_vault_raises_error_on_missing_args(self):

        def foo(vault):
            vault.remove_schedule()

        with self.assertRaises(TypeError):
            foo(self.vault)

        self.vault.remove_schedule.return_value = 'some schedule'
        with self.assertRaises(TypeError):
            foo(self.vault)

    def test_get_last_execution_time(self):

        def foo(vault):
            vault.get_last_execution_time(event_type='foo')

        foo(self.vault)

    def test_get_postings(self):

        def foo(vault):
            vault.get_postings()

        foo(self.vault)

    def test_get_client_transactions(self):

        def foo(vault):
            vault.get_client_transactions()

        foo(self.vault)

    def test_get_posting_batches(self):

        def foo(vault):
            vault.get_posting_batches()

        foo(self.vault)

    def test_add_account_note(self):

        def foo(vault):
            vault.add_account_note(
                body='some note',
                note_type='foo',
                is_visible_to_customer=True,
                date='some date'
            )

        foo(self.vault)

    def test_amend_schedule(self):

        def foo(vault):
            vault.amend_schedule(event_type='foo', new_schedule='bar')

        foo(self.vault)

    def test_get_account_creation_date(self):

        def foo(vault):
            vault.get_account_creation_date()

        foo(self.vault)

    def test_get_balance_timeseries(self):

        def foo(vault):
            vault.get_balance_timeseries()

        foo(self.vault)

    def test_get_hook_execution_id(self):

        def foo(vault):
            return vault.get_hook_execution_id()

        self.vault.get_hook_execution_id.return_value = '2127'
        hook_execution_id = foo(self.vault)
        self.vault.get_hook_execution_id.assert_called_once()
        self.assertEqual('2127', hook_execution_id)

    def test_get_parameter_timeseries(self):

        def foo(vault):
            vault.get_parameter_timeseries(name='foo')

        foo(self.vault)

    def test_get_flag_timeseries(self):

        def foo(vault):
            vault.get_flag_timeseries(flag='foo')

        foo(self.vault)

    def test_remove_schedule(self):

        def foo(vault):
            vault.remove_schedule(event_type='foo')

        foo(self.vault)

    def test_start_workflow(self):

        def foo(vault):
            vault.start_workflow(workflow=27, context='bob')

        foo(self.vault)

    def test_make_internal_transfer_instructions(self):

        def foo(vault):
            vault.make_internal_transfer_instructions(
                amount=10,
                denomination='GBP',
                client_transaction_id='1234',
                from_account_id='4444444',
                to_account_id='2222222'
            )

        foo(self.vault)

    def test_instruct_posting_batch(self):

        def foo(vault):
            vault.instruct_posting_batch(posting_instructions=[])

        foo(self.vault)

    def test_mock_vault_response_does_not_leak_flag_timeseries(self):

        def foo(vault):
            return vault.get_parameter_timeseries(name='foo')

        self.vault.get_flag_timeseries.return_value = 'other flags'
        response = foo(self.vault)
        self.assertNotEqual('other parameters', response)
        self.vault.get_parameter_timeseries.assert_called_once()
        self.vault.get_flag_timeseries.assert_not_called()

    def test_mock_vault_response_does_not_leak_parameter_timeseries(self):

        def foo(vault):
            return vault.get_flag_timeseries(flag='foo')

        self.vault.get_parameter_timeseries.return_value = 'other parameters'
        response = foo(self.vault)
        self.assertNotEqual('other flags', response)
        self.vault.get_flag_timeseries.assert_called_once()
        self.vault.get_parameter_timeseries.assert_not_called()
