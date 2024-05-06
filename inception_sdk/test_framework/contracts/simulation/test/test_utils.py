# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
import io

# TODO: we eval responses containing json statements. Should check why
import json  # noqa: F401
from datetime import datetime, timezone
from decimal import Decimal
from json.decoder import JSONDecodeError
from time import time
from unittest import TestCase, mock
from unittest.mock import MagicMock, Mock, call, mock_open, patch

# inception sdk
import inception_sdk.test_framework.contracts.simulation.utils as utils
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractNotificationResourceType,
    ExpectedContractNotification,
    ExpectedRejection,
    SimulationTestScenario,
    SubTest,
    SuperviseeConfig,
    SupervisorConfig,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
    create_supervisor_config,
    get_account_logs,
    get_balances,
    get_contract_contents,
    get_contract_notifications,
    get_flag_created,
    get_flag_definition_created,
    get_logs,
    get_logs_with_timestamp,
    get_num_postings,
    get_plan_assoc_created,
    get_plan_created,
    get_plan_logs,
    get_posting_instruction_batch,
    get_postings,
    get_processed_scheduled_events,
    print_json,
    print_log,
    print_postings,
)

SIMULATOR_RESPONSE_FILE = (
    "inception_sdk/test_framework/contracts/simulation/test/sample_simulator_response"
)
BACKDATED_SIMULATOR_RESPONSE_FILE = (
    "inception_sdk/test_framework/contracts/simulation/test/backdated_simulator_response"
)
SUPERVISOR_RESPONSE_FILE = (
    "inception_sdk/test_framework/contracts/simulation/test/sample_supervisor_response"
)


class TestSimulationTestCase(TestCase):
    @patch.object(SimulationTestCase, "contract_filepaths", ["contract_filepaths"])
    @patch.object(SimulationTestCase, "load_output_data")
    @patch.object(SimulationTestCase, "load_input_data")
    @patch.object(SimulationTestCase, "load_test_config")
    @patch.object(utils, "SmartContractRenderer")
    @patch.object(utils, "RendererConfig")
    @patch.object(utils, "is_file_renderable")
    @patch.object(utils, "load_module_from_filepath", MagicMock)
    def test_setup_class_calls_renderer(
        self,
        mock_is_file_renderable: Mock,
        mock_renderer_config: Mock,
        mock_renderer: Mock,
        mock_load_test_config_method: Mock,
        mock_load_input_data_method: Mock,
        mock_load_output_data_method: Mock,
    ):
        test_rendered_content = "test_rendered_content"

        mock_is_file_renderable.return_value = True
        mock_renderer_instance = Mock()
        mock_renderer.return_value = mock_renderer_instance
        mock_renderer_instance.rendered_contract = test_rendered_content

        SimulationTestCase.setUpClass()

        mock_renderer_config.assert_called_once_with(
            autogen_warning="# Code auto-generated for simulation testing",
            apply_formatting=False,
            use_git=False,
        )
        mock_renderer.assert_called_once()
        mock_renderer_instance.render.assert_called_once_with(write_to_file=False)

        mock_load_test_config_method.assert_called_once()
        mock_load_input_data_method.assert_called_once()
        mock_load_output_data_method.assert_called_once()

        self.assertEqual(SimulationTestCase.smart_contract_contents, [test_rendered_content])

    @patch.object(
        SimulationTestCase,
        "contract_filepaths",
        ["contract_template_1", "contract_filepath_1", "contract_template_2"],
    )
    @patch.object(SimulationTestCase, "load_output_data")
    @patch.object(SimulationTestCase, "load_input_data")
    @patch.object(SimulationTestCase, "load_test_config")
    @patch.object(utils, "SmartContractRenderer")
    @patch.object(utils, "RendererConfig")
    @patch.object(utils, "is_file_renderable")
    @patch.object(utils, "load_module_from_filepath", MagicMock)
    @patch("builtins.open", new_callable=mock_open, read_data="smart_contract_contents")
    def test_setup_class_calls_renderer_multiple_files(
        self,
        mock_open: Mock,
        mock_is_file_renderable: Mock,
        mock_renderer_config: Mock,
        mock_renderer: Mock,
        mock_load_test_config_method: Mock,
        mock_load_input_data_method: Mock,
        mock_load_output_data_method: Mock,
    ):
        mock_is_file_renderable.side_effect = [True, False, True]
        mock_renderer_instance = Mock()
        mock_renderer.return_value = mock_renderer_instance
        mock_renderer_instance.rendered_contract = "smart_contract_rendered_contents"

        SimulationTestCase.setUpClass()

        mock_renderer_config.assert_has_calls(
            [
                call(
                    autogen_warning="# Code auto-generated for simulation testing",
                    apply_formatting=False,
                    use_git=False,
                ),
                call(
                    autogen_warning="# Code auto-generated for simulation testing",
                    apply_formatting=False,
                    use_git=False,
                ),
            ]
        )
        self.assertEqual(mock_renderer.call_count, 2)
        mock_renderer_instance.render.assert_has_calls(
            [call(write_to_file=False), call(write_to_file=False)]
        )

        mock_load_test_config_method.assert_called_once()
        mock_load_input_data_method.assert_called_once()
        mock_load_output_data_method.assert_called_once()
        mock_open.assert_called_once()

        self.assertEqual(
            SimulationTestCase.smart_contract_contents,
            [
                "smart_contract_rendered_contents",
                "smart_contract_contents",
                "smart_contract_rendered_contents",
            ],
        )


class UtilsTest(SimulationTestCase):
    """
    This tests the integration test utils.
    """

    def setUp(self):
        self._started_at = time()
        sim_res_file = SIMULATOR_RESPONSE_FILE
        supervisor_res_file = SUPERVISOR_RESPONSE_FILE
        backdated_sim_res_file = BACKDATED_SIMULATOR_RESPONSE_FILE

        with open(sim_res_file, "r", encoding="utf-8") as simulator_response_file:
            self.sample_res = eval(simulator_response_file.read())

        with open(backdated_sim_res_file, "r", encoding="utf-8") as simulator_response_file:
            self.backdated_sample_res = eval(simulator_response_file.read())

        with open(supervisor_res_file, "r", encoding="utf-8") as simulator_response_file:
            self.supervisor_res = eval(simulator_response_file.read())

    def test_get_balances_for_undefined_dimensions(self):
        balances = get_balances(res=self.sample_res)
        internal_balances = balances["1"]

        date = datetime(2019, 1, 1, minute=1, tzinfo=timezone.utc)
        self.assertEqual(internal_balances.before(date)[BalanceDimensions("XYZ")].net, Decimal("0"))

    def test_get_balances_for_undefined_account(self):
        balances = get_balances(res=self.sample_res)
        xyz_balances = balances["xyz"]
        date = datetime(2019, 1, 1, minute=1, tzinfo=timezone.utc)
        self.assertEqual(xyz_balances.at(date)[BalanceDimensions()].net, Decimal("0"))

    def test_get_balances_for_undefined_date(self):
        balances = get_balances(res=self.sample_res)
        main_balances = balances["Main account"]
        date = datetime(2018, 1, 1, minute=1, tzinfo=timezone.utc)
        self.assertEqual(main_balances.at(date)[BalanceDimensions()].net, Decimal("0"))

    def test_get_balances_before_without_backdating(self):
        balances = get_balances(res=self.sample_res)
        main_balances = balances["Main account"]
        internal_balances = balances["1"]

        date = datetime(2019, 1, 1, minute=1, tzinfo=timezone.utc)
        self.assertEqual(main_balances.before(date)[BalanceDimensions()].net, Decimal("-110"))
        self.assertEqual(internal_balances.before(date)[BalanceDimensions()].net, Decimal("110"))

    def test_get_balances_at_without_backdating(self):
        balances = get_balances(res=self.sample_res)
        main_balances = balances["Main account"]
        internal_balances = balances["1"]

        date = datetime(2019, 1, 1, minute=1, tzinfo=timezone.utc)
        self.assertEqual(main_balances.at(date)[BalanceDimensions()].net, Decimal("-130"))
        self.assertEqual(internal_balances.at(date)[BalanceDimensions()].net, Decimal("130"))

    def test_get_balances_latest_without_backdating(self):
        balances = get_balances(res=self.sample_res)
        main_balances = balances["Main account"]
        internal_balances = balances["1"]

        self.assertEqual(main_balances.latest()[BalanceDimensions()].net, Decimal("1030"))
        self.assertEqual(internal_balances.latest()[BalanceDimensions()].net, Decimal("-1030"))

    def test_get_flag_definition_created(self):
        is_flag_created = get_flag_definition_created(
            res=self.sample_res, flag_definition_id="debug_flag"
        )

        self.assertTrue(is_flag_created)

    def test_get_flag_created(self):
        is_flag_applied_to_account = get_flag_created(
            res=self.sample_res,
            flag_definition_id="debug_flag",
            account_id="Main account",
        )

        self.assertTrue(is_flag_applied_to_account)

    def test_get_logs(self):
        logs = get_logs(res=self.sample_res)
        self.assertIn("created account", logs)
        self.assertIn("processed scheduled event", logs)

    def test_get_account_logs(self):
        account_logs_main = get_account_logs(res=self.sample_res, account_id="Main account")

        self.assertNotIn('account "1"', account_logs_main)
        self.assertIn('account "Main account"', account_logs_main)

        account_logs_1 = get_account_logs(res=self.sample_res, account_id="1")

        self.assertNotIn('account "Main account"', account_logs_1)
        self.assertIn('account "1"', account_logs_1)
        account_logs_supervisor = get_account_logs(
            res=self.supervisor_res, account_id="Savings Account"
        )

        self.assertNotIn('account "Checking Account"', account_logs_supervisor)
        self.assertIn('account "Savings Account"', account_logs_supervisor)

    def test_get_plan_logs(self):
        plan_logs_main = get_plan_logs(res=self.supervisor_res, plan_id="1")

        self.assertIn('plan "1"', plan_logs_main)
        self.assertIn('created plan "1"', plan_logs_main)
        self.assertIn(
            'created account plan association for account "Checking Account"',
            plan_logs_main,
        )
        self.assertNotIn('created account "Checking Account"', plan_logs_main)

    def test_get_plan_created(self):
        plan_created = get_plan_created(res=self.supervisor_res, plan_id="1")

        self.assertTrue(plan_created)

        plan_not_existing_id = get_plan_created(
            res=self.supervisor_res, plan_id="1", supervisor_version_id="5"
        )

        self.assertFalse(plan_not_existing_id)

    def test_get_plan_assoc_created(self):
        checking_account_plan_created = get_plan_assoc_created(
            res=self.supervisor_res, plan_id="1", account_id="Checking Account"
        )

        self.assertTrue(checking_account_plan_created)

        savings_account_plan_created = get_plan_assoc_created(
            res=self.supervisor_res, plan_id="1", account_id="Savings Account"
        )

        self.assertTrue(savings_account_plan_created)

        plan_not_created = get_plan_assoc_created(
            res=self.supervisor_res, plan_id="1", account_id="Youth Account"
        )

        self.assertFalse(plan_not_created)

    def test_get_logs_with_timestamp(self):
        all_logs = get_logs_with_timestamp(res=self.sample_res)
        timestamp_1 = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        timestamp_2 = datetime(year=2019, month=1, day=21, tzinfo=timezone.utc)

        self.assertIn("created flag definition", "".join(all_logs[timestamp_1]))
        self.assertNotIn("transactions must be in GBP", "".join(all_logs[timestamp_1]))
        self.assertIn("transactions must be in GBP", "".join(all_logs[timestamp_2]))

    def test_get_default_postings(self):
        postings = get_postings(res=self.sample_res)

        first_posting = postings[0]
        last_posting = postings[-1]

        self.assertEqual(first_posting["account_id"], "Main account")
        self.assertEqual(first_posting["account_address"], "DEFAULT")

        self.assertEqual(last_posting["account_id"], "Main account")
        self.assertEqual(last_posting["account_address"], "DEFAULT")

        postings_supervisor = get_postings(res=self.supervisor_res, account_id="Savings Account")

        first_posting = postings_supervisor[0]
        last_posting = postings_supervisor[-1]

        self.assertEqual(first_posting["account_id"], "Savings Account")
        self.assertEqual(first_posting["account_address"], "DEFAULT")

        self.assertEqual(last_posting["account_id"], "Savings Account")
        self.assertEqual(last_posting["account_address"], "DEFAULT")

    def test_get_posting_instruction_batch_at_with_one_result(self):
        account_id = "Main account"
        pibs = get_posting_instruction_batch(
            res=self.sample_res, event_type="outbound_hard_settlement"
        )

        self.assertListEqual(
            pibs[account_id].at(datetime(2019, 1, 1, tzinfo=timezone.utc)),
            [
                {
                    "amount": "110",
                    "denomination": "GBP",
                    "target_account": {"account_id": "Main account"},
                    "internal_account_id": "1",
                    "advice": False,
                    "target_account_id": "Main account",
                }
            ],
        )

    def test_get_posting_instruction_batch_at_with_multiple_results(self):
        account_id = "Easy Access Saver Account"
        pibs = get_posting_instruction_batch(res=self.sample_res, event_type="release")

        self.assertListEqual(
            pibs[account_id].at(datetime(2019, 3, 3, tzinfo=timezone.utc)),
            [
                {
                    "amount": "100",
                    "denomination": "GBP",
                    "target_account_id": "Easy Access Saver Account",
                    "internal_account_id": "DUMMY_DEPOSITING_ACCOUNT",
                },
                {
                    "amount": "50",
                    "denomination": "GBP",
                    "target_account_id": "Easy Access Saver Account",
                    "internal_account_id": "DUMMY_DEPOSITING_ACCOUNT",
                },
            ],
        )

    def test_get_posting_instruction_batch_latest(self):
        account_id = "Easy Access Saver Account"
        pibs = get_posting_instruction_batch(res=self.sample_res, event_type="release")

        self.assertListEqual(
            pibs[account_id].latest(),
            [
                {
                    "amount": "80",
                    "denomination": "GBP",
                    "target_account_id": "Easy Access Saver Account",
                    "internal_account_id": "DUMMY_DEPOSITING_ACCOUNT",
                }
            ],
        )

    def test_get_posting_instruction_batch_all(self):
        account_id = "Easy Access Saver Account"
        pibs = get_posting_instruction_batch(res=self.sample_res, event_type="release")

        self.assertEqual(len(pibs[account_id].all()), 2)

    def test_get_posting_instruction_batch_before(self):
        account_id = "Easy Access Saver Account"
        pibs = get_posting_instruction_batch(res=self.sample_res, event_type="release")

        self.assertEqual(len(pibs[account_id].before(datetime(2019, 3, 4, tzinfo=timezone.utc))), 2)

    def test_get_posting_instruction_batch_with_no_results(self):
        pibs = get_posting_instruction_batch(res=self.sample_res, event_type="INVALID")

        self.assertEqual(len(pibs), 0)

    def test_get_num_default_postings(self):
        num_postings = get_num_postings(
            res=self.sample_res, balance_dimensions=BalanceDimensions(address="DEFAULT")
        )
        self.assertEqual(num_postings, 4)

    def test_get_processed_scheduled_events(self):
        scheduled_events_timestamp = get_processed_scheduled_events(
            res=self.sample_res, event_id="ACCRUE_INTEREST", account_id="1"
        )

        self.assertEqual("2019-01-01T00:00:00Z", scheduled_events_timestamp[0])
        self.assertEqual("2019-01-02T00:00:00Z", scheduled_events_timestamp[1])
        self.assertEqual("2019-03-02T00:00:00Z", scheduled_events_timestamp[-1])

        supervised_events_timestamp = get_processed_scheduled_events(
            res=self.supervisor_res,
            event_id="PUBLISH_COMBINED_EXTRACT",
            plan_id="1",
        )

        self.assertEqual("2020-05-12T23:59:00Z", supervised_events_timestamp[0])
        self.assertEqual("2020-05-13T23:59:00Z", supervised_events_timestamp[1])
        self.assertEqual("2020-06-30T23:59:00Z", supervised_events_timestamp[-1])

    def test_get_contract_notifications(self):
        notifications = get_contract_notifications(res=self.sample_res)
        self.assertEqual(
            notifications,
            {
                "Easy Access Saver Account": {
                    "my_notification": (
                        [
                            (
                                datetime(2019, 3, 4, tzinfo=timezone.utc),
                                {
                                    "notification_type": "my_notification",
                                    "resource_id": "Easy Access Saver Account",
                                    "resource_type": "RESOURCE_ACCOUNT",
                                    "notification_details": {"some_key": "some_value"},
                                },
                            ),
                            (
                                datetime(2019, 3, 5, tzinfo=timezone.utc),
                                {
                                    "notification_type": "my_notification",
                                    "resource_id": "Easy Access Saver Account",
                                    "resource_type": "RESOURCE_ACCOUNT",
                                    "notification_details": {"some_key": "some_value"},
                                },
                            ),
                            (
                                datetime(2019, 3, 6, tzinfo=timezone.utc),
                                {
                                    "notification_type": "my_notification",
                                    "resource_id": "Easy Access Saver Account",
                                    "resource_type": "RESOURCE_ACCOUNT",
                                    "notification_details": {"some_key": "some_value"},
                                },
                            ),
                            (
                                datetime(2019, 3, 6, tzinfo=timezone.utc),
                                {
                                    "notification_type": "my_notification",
                                    "resource_id": "Easy Access Saver Account",
                                    "resource_type": "RESOURCE_ACCOUNT",
                                    "notification_details": {"some_key": "some_value"},
                                },
                            ),
                        ]
                    )
                }
            },
        )

    def test_check_contract_notifications_match(self):
        notifications = get_contract_notifications(self.sample_res)
        self.assertIsNone(
            self.check_contract_notifications(
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        datetime(2019, 3, 5, tzinfo=timezone.utc),
                        "my_notification",
                        notification_details={"some_key": "some_value"},
                        resource_id="Easy Access Saver Account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
                contract_notifications=notifications,
            )
        )

    def test_check_contract_notifications_partial_match(self):
        notifications = get_contract_notifications(self.sample_res)
        with self.assertRaises(AssertionError) as ctx:
            self.check_contract_notifications(
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=datetime(2019, 3, 5, tzinfo=timezone.utc),
                        notification_type="my_notification",
                        # these details don't match
                        notification_details={"some_other_key": "some_other_value"},
                        resource_id="Easy Access Saver Account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
                contract_notifications=notifications,
            )
        self.assertIn(
            "Notification found for type and resource id but with different details: "
            "{'some_key': 'some_value'}.\\nExpected {'some_other_key': 'some_other_value'}",
            str(ctx.exception),
        )

    def test_check_contract_notifications_no_match(self):
        notifications = get_contract_notifications(self.sample_res)
        with self.assertRaises(AssertionError) as ctx:
            self.check_contract_notifications(
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        # wrong time so we get no match at all
                        timestamp=datetime(2019, 3, 5, minute=1, tzinfo=timezone.utc),
                        notification_type="my_notification",
                        notification_details={"some_other_key": "some_other_value"},
                        resource_id="Easy Access Saver Account",
                        resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
                    )
                ],
                contract_notifications=notifications,
            )
        self.assertIn(
            "No notification found for this type and resource id at 2019-03-05 00:01:00+00:00'",
            str(ctx.exception),
        )

    def test_check_parameter_change_rejections_match(self):
        self.assertIsNone(
            self.check_parameter_change_rejections(
                expected_rejections=[
                    ExpectedRejection(
                        timestamp=datetime(2019, 3, 5, tzinfo=timezone.utc),
                        rejection_type="dummy_rejection_type",
                        rejection_reason="dummy_rejection_reason",
                    )
                ],
                logs_with_timestamp={
                    datetime(2019, 3, 5, tzinfo=timezone.utc): [
                        "account parameters update rejected: dummy_rejection_reason"
                    ]
                },
            )
        )

    def test_check_parameter_change_rejections_different_reason_no_match(self):
        test_rejection = ExpectedRejection(
            timestamp=datetime(2019, 3, 5, tzinfo=timezone.utc),
            rejection_type="dummy_rejection_type",
            rejection_reason="dummy_rejection_reason",
        )
        with self.assertRaises(AssertionError) as ctx:
            self.check_parameter_change_rejections(
                expected_rejections=[test_rejection],
                logs_with_timestamp={
                    datetime(2019, 3, 5, tzinfo=timezone.utc): [
                        "account parameters update rejected: other_rejection_reason"
                    ]
                },
            )
        self.assertIn(
            f"expected values not found: {[test_rejection]}",
            str(ctx.exception),
        )

    def test_check_parameter_change_rejections_different_date_no_match(self):
        test_rejection = ExpectedRejection(
            timestamp=datetime(2019, 3, 5, tzinfo=timezone.utc),
            rejection_type="dummy_rejection_type",
            rejection_reason="dummy_rejection_reason",
        )
        with self.assertRaises(AssertionError) as ctx:
            self.check_parameter_change_rejections(
                expected_rejections=[test_rejection],
                logs_with_timestamp={
                    datetime(2019, 3, 5, 1, tzinfo=timezone.utc): [
                        "account parameters update rejected: dummy_rejection_reason"
                    ]
                },
            )
        self.assertIn(
            f"expected values not found: {[test_rejection]}",
            str(ctx.exception),
        )

    def test_print_json(self):
        output = sys_stdout(print_json, "debug", self.sample_res)

        self.assertIn("debug", output)
        self.assertIn("account_notes", output)
        self.assertIn("balances", output)

    def test_print_postings(self):
        output = sys_stdout(print_postings, res=self.sample_res)

        self.assertIn("account_address", output)
        self.assertNotIn("balances", output)

    def test_print_log(self):
        output = sys_stdout(print_log, res=self.sample_res)
        self.assertIn("flag", output)
        self.assertNotIn("1030", output)

    def test_run_test_scenario_no_configs(self):
        with self.assertRaises(ValueError) as ctx:
            self.run_test_scenario(
                SimulationTestScenario(
                    sub_tests=[], start=datetime(2020, 1, 1), end=datetime(2020, 1, 2)
                )
            )
        self.assertEqual(
            ctx.exception.args[0], "Test scenario must have supervisor or contract config!"
        )

    @mock.patch.object(utils, "compile_chrono_events")
    @mock.patch.object(utils, "load_file_contents")
    def test_run_test_scenario_supervisor_config(
        self, load_file_contents_mock, compile_chrono_events_mock
    ):
        compile_chrono_events_mock.return_value = [], []
        load_file_contents_mock.side_effect = lambda x: x + "_contents"
        supervisor_config = SupervisorConfig(
            supervisor_file_path="supervisor_contract_file_path",
            supervisor_contract_version_id="supervisor_contract_version_id",
            supervisee_contracts=[
                ContractConfig(
                    clu_resource_id="contract_id_1",
                    contract_file_path="contract_file_1",
                    template_params={},
                    smart_contract_version_id="contract_id_1_version",
                    account_configs=[
                        AccountConfig(
                            account_id_base="contract_id_1_account",
                            instance_params={},
                            number_of_accounts=1,
                        )
                    ],
                ),
                ContractConfig(
                    clu_resource_id="contract_id_2",
                    contract_file_path="contract_file_2",
                    template_params={},
                    smart_contract_version_id="contract_id_2_version",
                    account_configs=[
                        AccountConfig(
                            account_id_base="contract_id_2_account",
                            instance_params={},
                            number_of_accounts=2,
                        )
                    ],
                ),
            ],
        )
        with mock.patch.object(self, "client") as client_mock:
            client_mock.simulate_smart_contract.return_value = []
            self.run_test_scenario(
                SimulationTestScenario(
                    sub_tests=[],
                    start=datetime(2020, 1, 1),
                    end=datetime(2020, 1, 2),
                    supervisor_config=supervisor_config,
                )
            )
        client_mock.simulate_smart_contract.assert_called_with(
            start_timestamp=datetime(2020, 1, 1),
            end_timestamp=datetime(2020, 1, 2),
            supervisor_contract_code="supervisor_contract_file_path_contents",
            supervisor_contract_version_id="supervisor_contract_version_id",
            supervisee_version_id_mapping={
                "contract_id_1": "contract_id_1_version",
                "contract_id_2": "contract_id_2_version",
            },
            contract_codes=["contract_file_1_contents", "contract_file_2_contents"],
            smart_contract_version_ids=["contract_id_1_version", "contract_id_2_version"],
            templates_parameters=[{}, {}],
            internal_account_ids=None,
            supervisor_contract_config=supervisor_config,
            contract_config=None,
            events=[],
            output_account_ids=[],
            output_timestamps=[],
            debug=False,
        )

    @mock.patch.object(utils, "compile_chrono_events")
    @mock.patch.object(utils, "load_file_contents")
    def test_run_test_scenario_error_expectation(
        self, load_file_contents_mock, compile_chrono_events_mock
    ):
        compile_chrono_events_mock.return_value = [], []
        load_file_contents_mock.side_effect = lambda x: x + "_contents"
        sample_config = ContractConfig(
            clu_resource_id="contract_id_1",
            contract_file_path="contract_file_1",
            template_params={},
            smart_contract_version_id="contract_id_1_version",
            account_configs=[
                AccountConfig(
                    account_id_base="contract_id_1_account",
                    instance_params={},
                    number_of_accounts=1,
                )
            ],
        )
        base_scenario = SimulationTestScenario(
            sub_tests=[],
            start=datetime(2020, 1, 1),
            end=datetime(2020, 1, 2),
            contract_config=sample_config,
        )

        with self.subTest("rejects_simultaneous_expectations_and_errors"):
            mock_exception = ValueError("dummy error")
            sub_tests = [
                SubTest(
                    description="expectation 1",
                    expected_balances_at_ts={datetime(2020, 1, 1): {"key": "val"}},
                )
            ]

            self.assertRaisesRegex(
                ValueError,
                "Test scenario should not contain expectations when a simulation error is expected",
                self.run_test_scenario,
                SimulationTestScenario(
                    sub_tests=sub_tests,
                    start=datetime(2020, 1, 1),
                    end=datetime(2020, 1, 2),
                    contract_config=sample_config,
                ),
                expected_simulation_error=mock_exception,
            )

        with self.subTest("expected_exception_raises_no_errors"):
            mock_exception = ValueError("dummy error")

            # test will fail if a exception is raised here
            with mock.patch.object(self, "client") as client_mock:
                client_mock.simulate_smart_contract.side_effect = Mock(side_effect=mock_exception)
                self.run_test_scenario(
                    base_scenario,
                    expected_simulation_error=mock_exception,
                )

        with self.subTest("mismatched_exception_raises_error"):
            exp_exception = ValueError("{'1':'dummy error'}")
            client_exception = ValueError("{'2' :'some other error'}")

            with mock.patch.object(self, "client") as client_mock:
                client_mock.simulate_smart_contract.side_effect = Mock(side_effect=client_exception)
                self.assertRaisesRegex(
                    AssertionError,
                    "expected values not found:",
                    self.run_test_scenario,
                    base_scenario,
                    expected_simulation_error=exp_exception,
                )

        with self.subTest("value_error_raised_on_non_dict_expected_exception"):
            exp_exception = ValueError("not a dict")
            client_exception = ValueError("{'2' :'some other error'}")

            with mock.patch.object(self, "client") as client_mock:
                client_mock.simulate_smart_contract.side_effect = Mock(side_effect=client_exception)
                self.assertRaisesRegex(
                    ValueError,
                    "Exception must be in a valid JSON format:",
                    self.run_test_scenario,
                    base_scenario,
                    expected_simulation_error=exp_exception,
                )

        with self.subTest("value_error_raised_on_non_dict_returned_exception"):
            exp_exception = ValueError("{'1':'dummy error'}")
            client_exception = ValueError("not a dict")

            with mock.patch.object(self, "client") as client_mock:
                client_mock.simulate_smart_contract.side_effect = Mock(side_effect=client_exception)
                self.assertRaisesRegex(
                    ValueError,
                    "returned error is not in a JSON format:",
                    self.run_test_scenario,
                    base_scenario,
                    expected_simulation_error=exp_exception,
                )

        with self.subTest("value_error_raised_on_non_dict_returned_exception"):
            exp_exception = ValueError("{'1':'dummy error'}")
            client_exception = Exception("{'1':'dummy error'}")
            with mock.patch.object(self, "client") as client_mock:
                client_mock.simulate_smart_contract.side_effect = Mock(side_effect=client_exception)
                self.assertRaisesRegex(
                    AssertionError,
                    "Expection type mismatch:",
                    self.run_test_scenario,
                    base_scenario,
                    expected_simulation_error=exp_exception,
                )

        with self.subTest("simulation_returned_error_when_non_expected_gives_original_error"):
            exp_exception = None
            client_exception = JSONDecodeError("Expecting Value", "Some non standard error", 0)
            with mock.patch.object(self, "client") as client_mock:
                client_mock.simulate_smart_contract.side_effect = Mock(side_effect=client_exception)
                self.assertRaisesRegex(
                    AssertionError,
                    "Some non standard error",
                    self.run_test_scenario,
                    base_scenario,
                    expected_simulation_error=exp_exception,
                )


def sys_stdout(func, *args, **kwargs):
    with patch("sys.stdout", new=io.StringIO()) as sys_out:
        func(*args, **kwargs)
        return sys_out.getvalue()


class TestGetContractContents(TestCase):
    def test_get_prepopulated_contract_content(self):
        test_content = "some_content"
        contract_configs = [
            ContractConfig(template_params={}, account_configs=[], contract_content=test_content)
        ]
        contents = get_contract_contents(contract_configs)
        self.assertEqual(contents, [test_content])

    @patch("inception_sdk.test_framework.contracts.simulation.utils.load_file_contents")
    def test_get_file_contract_content(self, mock_load_file_contents_method: Mock):
        test_content = "some_content"
        mock_load_file_contents_method.return_value = test_content

        contract_configs = [
            ContractConfig(template_params={}, account_configs=[], contract_file_path="some_path")
        ]
        contents = get_contract_contents(contract_configs)
        self.assertEqual(contents, [test_content])


class TestDataObjects(TestCase):
    def test_contract_config_must_have_at_least_one_source(self):
        with self.assertRaises(ValueError) as e:
            ContractConfig(template_params={}, account_configs=[])

        self.assertEqual(
            str(e.exception),
            "Neither contract_file_path or contract_content has been provided.",
        )

    def test_create_supervisor_config(self):
        supervisee_1 = SuperviseeConfig(
            contract_id="contract_id_1",
            contract_file="contract_file_1",
            account_name="Account 1",
            version="1",
            instance_parameters={"a": "1"},
            template_parameters={"b": "2"},
            instances=3,
        )

        supervisee_2 = SuperviseeConfig(
            contract_id="contract_id_2",
            contract_file="contract_file_2",
            account_name="Account 1",
            version="2",
            instance_parameters={"c": "3"},
            template_parameters={"d": "4"},
            instances=4,
        )

        supervisor_contract = "supervisor_contract"
        supervisor_contract_version_id = "supervisor_contract_version_id"

        supervisor_config = create_supervisor_config(
            supervisor_contract=supervisor_contract,
            supervisor_contract_version_id=supervisor_contract_version_id,
            supervisees=[supervisee_1, supervisee_2],
        )

        # check supervisor config
        self.assertIsInstance(supervisor_config, SupervisorConfig)

        self.assertEqual(supervisor_config.supervisor_file_path, supervisor_contract)
        self.assertEqual(
            supervisor_config.supervisor_contract_version_id,
            supervisor_contract_version_id,
        )

        # check supervisee contracts
        self.assertEqual(len(supervisor_config.supervisee_contracts), 2)

        # check supervisee contract configs
        expected_supervisee_contracts = [supervisee_1, supervisee_2]
        for i, supervisee_contract in enumerate(supervisor_config.supervisee_contracts):
            self.assertEqual(
                supervisee_contract.clu_resource_id, expected_supervisee_contracts[i].contract_id
            )
            self.assertEqual(
                supervisee_contract.contract_file_path,
                expected_supervisee_contracts[i].contract_file,
            )
            self.assertDictEqual(
                supervisee_contract.template_params,
                expected_supervisee_contracts[i].template_parameters,
            )
            self.assertEqual(
                supervisee_contract.smart_contract_version_id,
                expected_supervisee_contracts[i].version,
            )
            self.assertEqual(len(supervisee_contract.account_configs), 1)

            supervisee_contract_account = supervisee_contract.account_configs[0]
            self.assertEqual(
                supervisee_contract_account.account_id_base,
                f"{expected_supervisee_contracts[i].account_name} ",
            )
            self.assertDictEqual(
                supervisee_contract_account.instance_params,
                expected_supervisee_contracts[i].instance_parameters,
            )
            self.assertEqual(
                supervisee_contract_account.number_of_accounts,
                expected_supervisee_contracts[i].instances,
            )
