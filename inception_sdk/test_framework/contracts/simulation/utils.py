# Copyright @ 2021-2023 Thought Machine Group Limited. All rights reserved.
# standard libs
import ast
import json
import logging
import os
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from dateutil import parser
from decimal import Decimal
from json.decoder import JSONDecodeError
from pathlib import Path
from time import time
from typing import Any, Callable, DefaultDict, Generator
from unittest import TestCase

# third party
from semantic_version import Version

# inception sdk
import inception_sdk.common.python.flag_utils as flag_utils
from inception_sdk.common.python.file_utils import load_file_contents, load_module_from_filepath
from inception_sdk.test_framework.common.balance_helpers import (
    Balance,
    BalanceDimensions,
    compare_balances,
)
from inception_sdk.test_framework.common.config import (
    EnvironmentPurpose,
    extract_framework_environments_from_config,
)
from inception_sdk.test_framework.common.timeseries import TimeSeries
from inception_sdk.test_framework.contracts.simulation import vault_caller
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ExpectedContractNotification,
    ExpectedDerivedParameter,
    ExpectedRejection,
    ExpectedSchedule,
    SimulationEvent,
    SimulationTestScenario,
    SubTest,
    SuperviseeConfig,
    SupervisorConfig,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.events.parameter_events import (
    CreateGlobalParameterEvent,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    get_contract_setup_events,
    get_supervisor_setup_events,
)
from inception_sdk.tools.renderer.render_utils import is_file_renderable
from inception_sdk.tools.renderer.renderer import RendererConfig, SmartContractRenderer

DEFAULT = "DEFAULT"
MAIN_ACCOUNT = "Main account"

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def skipForVaultVersion(callback: Callable[[Version], bool] | None = None, reason=None):
    def decorator(method):
        def inner(ref: SimulationTestCase):
            version: Version = ref.get_vault_version()
            if callback is None:
                skip_reason = reason or "This test should be skipped for all versions of Vault."
                # This raises an exception.
                ref.skipTest(skip_reason)
            is_skip = callback(version)
            if is_skip:
                skip_reason = reason or f"This test should be skipped for Vault v{str(version)}."
                # This raises an exception.
                ref.skipTest(skip_reason)
            return method(ref)

        return inner

    return decorator


class SimulationTestCase(TestCase):
    contract_filepaths: list[str] = []
    input_data_filename: str = ""
    expected_output_filename: str = ""
    default_instance_params = None
    default_template_params = None
    internal_accounts = None
    smart_contract_path_to_content: dict[str, str] = {}

    @classmethod
    def load_contract_from_file(cls):
        # TODO (INC-5497): Remove references to smart_contract_contents in favor of using
        # smart_contract_path_to_content mapping so that we aren't loading and storing the contract
        # file on every sim test. (run_test_scenario can now reliably look up contract contents if
        # they have already been loaded)
        cls.smart_contract_contents = []
        for contract in cls.contract_filepaths:
            if is_file_renderable(Path(contract)):
                scr_config = RendererConfig(
                    autogen_warning="# Code auto-generated for simulation testing",
                    apply_formatting=False,
                    use_git=False,
                )
                scr = SmartContractRenderer(load_module_from_filepath(contract), scr_config)
                scr.render(write_to_file=False)
                cls.smart_contract_contents.append(scr.rendered_contract)
                cls.smart_contract_path_to_content.update({contract: scr.rendered_contract})

            else:
                with open(contract, encoding="utf-8") as smart_contract_file:
                    contract_content = smart_contract_file.read()
                    cls.smart_contract_contents.append(contract_content)
                    cls.smart_contract_path_to_content.update({contract: contract_content})

    @classmethod
    def load_test_config(cls):
        # we allow unknown because there may be unittest flags in argv
        flag_utils.parse_flags(allow_unknown=True)
        environment, _ = extract_framework_environments_from_config(
            environment_purpose=EnvironmentPurpose.SIM
        )
        core_api_url = environment.core_api_url
        auth_token = environment.service_account.token
        if not core_api_url or not auth_token:
            raise ValueError(
                "core_api_url and/or service_account.token not found in specified config"
            )
        cls.client = vault_caller.Client(core_api_url=core_api_url, auth_token=auth_token)

    @classmethod
    def load_input_data(cls):
        if cls.input_data_filename:
            with open(cls.input_data_filename, encoding="utf-8") as input_data_file:
                cls.input_data = json.load(input_data_file)
        else:
            cls.input_data = {}

    @classmethod
    def load_output_data(cls):
        if cls.expected_output_filename:
            with open(cls.expected_output_filename, encoding="utf-8") as expected_output_file:
                cls.expected_output = json.load(expected_output_file)
        else:
            cls.expected_output = {}

    @classmethod
    def setUpClass(cls):
        # This ensures we get full balance diffs when using check_balances
        cls.maxDiff = None

        cls.load_contract_from_file()

        cls.load_test_config()

        cls.load_input_data()

        cls.load_output_data()

    def setUp(self):
        self._started_at = time()

    def tearDown(self):
        self._elapsed_time = time() - self._started_at
        # Uncomment this for timing info.
        # print('{} ({}s)'.format(self.id().rpartition('.')[2], round(self._elapsed_time, 2))

    def assertBalancesEqual(
        self,
        expected_balances: list[tuple[BalanceDimensions, str]],
        actual_balances: DefaultDict[BalanceDimensions, Balance],
        msg: str = "",
    ) -> None:
        """
        Fail if the balances for the given dimensions do not match expected values:
        :param expected_balances: balance dimensions and corresponding expected net values
        :param actual_balances: default dict of balance dimensions and corresponding actual
        balances
        :param msg: message to show on assertion failure. The differences between expected and
        actual balances will be appended to this
        """
        self.assertExpectations(expected_balances, actual_balances, compare_balances, msg)

    def assertExpectations(
        self,
        expected: Any,
        actual: Any,
        comparator: Callable[[Any, Any], dict | list],
        msg: str = "",
    ) -> None:
        """
        Fails if actual values do not match expected values
        :param expected: objects specifying expected values
        :param actual: objects that contains actual outcome from the simulator
        :param comparator: callable that takes in expected and actual as arguements, and returns
        a collection of expected values not found in actual
        :param msg: message to show on assertion failure. The differences between expected and
        actual will be appended to this
        """
        failed_expectations = comparator(expected, actual)
        if len(failed_expectations) > 0:
            raise AssertionError((msg or "expected values not found") + f": {failed_expectations}")

    @staticmethod
    def assertions_exist_in_subtests(subtests: list[SubTest]):
        """
        Checks if there exists any subtest assertions in a given list of subtests

        :param subtests: list of subtests, commonly defined as SimulationTestScenario.subtests
        :return: `True` if assertions exists in the Subtests, otherwise `False`
        """
        for sub_test in subtests:
            possible_expectations = [
                sub_test.expected_balances_at_ts,
                sub_test.expected_schedules,
                sub_test.expected_posting_rejections,
                sub_test.expected_parameter_change_rejections,
                sub_test.expected_derived_parameters,
                sub_test.expected_contract_notifications,
            ]
            if any(possible_expectations):
                return True
        return False

    def check_balances(
        self,
        expected_balances: dict[str, dict[datetime, list[tuple[BalanceDimensions, str]]]],
        actual_balances: DefaultDict[str, TimeSeries],
    ) -> None:
        """
        Simplifies balance checking inside simulation tests. Does not support backdated tests
        :param expected_balances: Expected balances structured as follows. The datetime represents
        value_timestamp
        {
            'account_id': {
                datetime(2020, 1, 1,): [
                    (BalanceDimensions(), '0'),
                    (BalanceDimensions(address='CUSTOM_ADDRESS), '10')
                ]
            }
        }
        :param actual_balances: actual balances as returned by get_balances
        """
        for account_id, account_expected_balances in expected_balances.items():
            account_balances = actual_balances[account_id]
            for value_timestamp, balance_tuples in account_expected_balances.items():
                self.assertBalancesEqual(
                    expected_balances=balance_tuples,
                    actual_balances=account_balances.at(value_timestamp),
                    msg=f"expected & actual balances differ for {account_id} at {value_timestamp}",
                )

    def check_balances_by_ts(
        self,
        expected_balances: dict[datetime, dict[str, list[tuple[BalanceDimensions, str]]]],
        actual_balances: DefaultDict[str, TimeSeries],
        description: str = "",
    ) -> None:
        """
        Similar to check_balances, except allows the expected balances to be organised by timestamp
        and then account, instead of account and then timestamp. This is helpful to improve
        legibility of tests that check multiple accounts' balances
        :param expected_balances: Expected balances structured as follows. The datetime represents
        value_timestamp
        {
            datetime(2020, 1, 1) : {
                'account_id': [
                    (BalanceDimensions(), '0'),
                    (BalanceDimensions(address='CUSTOM_ADDRESS), '10')
                ]
            }
        }
        :param actual_balances: actual balances as returned by get_balances
        :param description: msg for assertion errors
        """
        for value_timestamp, account_expected_balances in expected_balances.items():
            for account_id, balance_tuples in account_expected_balances.items():
                account_balances = actual_balances[account_id]
                self.assertBalancesEqual(
                    expected_balances=balance_tuples,
                    actual_balances=account_balances.at(value_timestamp),
                    msg=(
                        description
                        or f"expected and actual balances differ "
                        f"for {account_id} at {value_timestamp}"
                    ),
                )

    def check_derived_parameters(
        self,
        expected_derived_parameters: list[ExpectedDerivedParameter],
        derived_parameters: dict[str, TimeSeries],
        description: str = "",
    ) -> None:
        def get_mismatched_derived_params(expected_derived_parameters, actual_derived_parameters):
            mismatched_derived_params = {}
            for expected_derived_param in expected_derived_parameters:
                account_id = expected_derived_param.account_id
                value_timestamp = expected_derived_param.timestamp
                parameter = expected_derived_param.name
                expected_value = expected_derived_param.value
                actual_derived_params = actual_derived_parameters[account_id].at(value_timestamp)
                if parameter not in actual_derived_params:
                    mismatched_derived_params[
                        parameter
                    ] = "ERROR: parameter is missing from actual values"
                elif expected_value != actual_derived_params[parameter]:
                    mismatched_derived_params[
                        f'param: "{parameter}" '
                        f'account: "{account_id}" '
                        f'@: "{str(value_timestamp)}"'
                    ] = f'Expected: "{expected_value}" Got: "{actual_derived_params[parameter]}"'
            return mismatched_derived_params

        self.assertExpectations(
            expected_derived_parameters,
            derived_parameters,
            get_mismatched_derived_params,
            description,
        )

    def check_posting_rejections(
        self,
        expected_rejections: list[ExpectedRejection],
        logs_with_timestamp: dict,
        description: str = "",
    ) -> None:
        def get_missing_rejections(expected_rejections, logs_with_timestamp):
            return [
                expected_rejection
                for expected_rejection in expected_rejections
                if not any(
                    f'account "{expected_rejection.account_id}" rejected with '
                    f'rejection type "{expected_rejection.rejection_type}" and '
                    f'reason "{expected_rejection.rejection_reason}' in log
                    for log in logs_with_timestamp.get(expected_rejection.timestamp, [])
                )
            ]

        self.assertExpectations(
            expected_rejections,
            logs_with_timestamp,
            get_missing_rejections,
            description,
        )

    def check_parameter_change_rejections(
        self,
        expected_rejections: list[ExpectedRejection],
        logs_with_timestamp: dict,
        description: str = "",
    ) -> None:
        """
        Validates that all expected parameter change rejections are present in the log of the
        response to the simulate API

        :param expected_rejections: rejections that should be generated during the simulation
        :param logs_with_timestamp: logs retrieved from the result of calling the API
        :param description: description of the subtest used to identify the subtest in case the
        assertion fails
        """

        def get_missing_rejections(expected_rejections, logs_with_timestamp):
            return [
                expected_rejection
                for expected_rejection in expected_rejections
                if not any(
                    f"account parameters update rejected: {expected_rejection.rejection_reason}"
                    in log
                    for log in logs_with_timestamp.get(expected_rejection.timestamp, [])
                )
            ]

        self.assertExpectations(
            expected_rejections,
            logs_with_timestamp,
            get_missing_rejections,
            description,
        )

    def check_simulation_error(
        self,
        expected_error: Exception | None = None,
        actual_error: Exception | None = None,
    ):
        """
        Matches a simulation error to a expected simulation error.
        Both Error strings should be dict parsable.
        Compares the available keys found in the expected error against the actual error.
        :param expected_error: the expected error from a simulation.
        :param actual_error: the actual error recieved from the simulation.
        """

        def parse_err(error_str):
            captured_exception: Exception | None = None
            try:
                return json.loads(str(error_str).replace("'", '"'))
            except Exception as e:
                captured_exception = e
            if isinstance(captured_exception, JSONDecodeError):
                # fallback to AST parsing
                try:
                    return ast.literal_eval(str(error_str))
                except Exception:
                    pass
            # Re-raise the captured exception if the fallback did not work
            raise captured_exception

        def _repr_err(err):
            err_str = str(err)
            # This is needed as the original payload gets obfuscated by the error itself.
            if isinstance(err, JSONDecodeError):
                err_str += "\n" + err.doc
            return err_str

        # skip check if quick check
        if expected_error == actual_error:
            return

        # Check exception types match:
        # None will resolve to NoneType
        exp_err_type = expected_error.__class__.__name__
        act_err_type = actual_error.__class__.__name__

        if exp_err_type != act_err_type:
            raise AssertionError(
                f"Expection type mismatch: Expected simulation error:"
                f"{exp_err_type}, Got: {act_err_type}"
                f"Error: {_repr_err(actual_error)}"
            )

        def compare_errors(expected, actual):
            try:
                expected_error_dict = parse_err(expected)
            except JSONDecodeError:
                raise ValueError(f"Exception must be in a valid JSON format: {_repr_err(expected)}")
            try:
                actual_error_dict = parse_err(actual)
            except JSONDecodeError:
                raise ValueError(f"returned error is not in a JSON format:{_repr_err(actual)}")

            # pad missing keys with empty values to avoid key errors
            for key in expected_error_dict:
                if key not in actual_error_dict:
                    actual_error_dict[key] = None
            return {
                param: {
                    "expected": expected_error_dict[param],
                    "actual": actual_error_dict[param],
                }
                for param in expected_error_dict
                if expected_error_dict[param] != actual_error_dict[param]
            }

        self.assertExpectations(
            expected=expected_error,
            actual=actual_error,
            comparator=compare_errors,
        )

    def check_schedule_processed(
        self,
        expected_schedule_runs: list[ExpectedSchedule],
        res: list[dict[str, Any]],
        description: str = "",
    ) -> None:
        def get_missing_schedule_runs(expected_schedules, simulator_results):
            missing_schedule_runs = []
            for expected_schedule in expected_schedules:
                processed_schedules = get_processed_scheduled_events(
                    simulator_results,
                    expected_schedule.event_id,
                    account_id=expected_schedule.account_id,
                    plan_id=expected_schedule.plan_id,
                )
                if expected_schedule.count is not None:
                    self.assertEqual(expected_schedule.count, len(processed_schedules), description)

                missing_schedule_runs.extend(
                    (
                        expected_schedule_run
                        for expected_schedule_run in expected_schedule.run_times
                        if (
                            expected_schedule_run.strftime("%Y-%m-%dT%H:%M:%SZ")
                            not in processed_schedules
                        )
                    )
                )
            return missing_schedule_runs

        self.assertExpectations(expected_schedule_runs, res, get_missing_schedule_runs, description)

    def check_contract_notifications(
        self,
        expected_contract_notifications: list[ExpectedContractNotification],
        contract_notifications: dict[str, dict[str, list]],
        description: str = "",
    ) -> None:
        def get_mismatched_notifications(
            expected_notifications: list[ExpectedContractNotification],
            actual_notifications: dict[str, dict[str, list]],
        ):
            mismatched_notifications = []
            for expected_notification in expected_notifications:
                potential_match_notifications = actual_notifications[
                    expected_notification.resource_id
                ][expected_notification.notification_type]

                potential_match = {}
                for notification in potential_match_notifications:
                    # Comparing timestamps
                    if notification[0] == expected_notification.timestamp:
                        potential_match = notification[1]
                        # Comparing notification details
                        if (
                            potential_match["notification_details"]
                            == expected_notification.notification_details
                        ):
                            break
                        else:
                            mismatched_notifications.append(
                                f"Notification found for type and resource id but with different "
                                f"details: {potential_match.get('notification_details')}.\n"
                                f"Expected {expected_notification.notification_details}"
                            )
                # No match found for the expected_notification in actual_notifications
                if not potential_match:
                    mismatched_notifications.append(
                        f"No notification found for this type and resource id at "
                        f"{expected_notification.timestamp}"
                    )

            return mismatched_notifications

        self.assertExpectations(
            expected_contract_notifications,
            contract_notifications,
            get_mismatched_notifications,
            description,
        )

    def run_test_scenario(
        self,
        test_scenario: SimulationTestScenario,
        expected_simulation_error: Exception | None = None,
        smart_contracts: list | None = None,
    ):
        """
        run_test_scenario will run the provided test case scenario.
        The platform erroneously returns an API rejection instead of a simulation result
        when Rejections are returned in hooks other than pre-posting.
        Consequently no Sub-Test expectations may be set if a simulation error is expected.

        """
        setup_events: list[SimulationEvent] = []
        smart_contracts = [] if smart_contracts is None else smart_contracts
        supervisor_contract_code = None
        supervisee_version_id_mapping = None
        supervisor_contract_version_id = None
        supervisor_contract_config = None

        if test_scenario.contract_config and test_scenario.supervisor_config:
            log.warning(
                "Both supervisor and contract config detected, "
                "setup events will be based on supervisor config"
            )

        elif test_scenario.supervisor_config:
            setup_events.extend(get_supervisor_setup_events(test_scenario))
            if test_scenario.supervisor_config.supervisor_file_path:
                supervisor_contract_code = load_file_contents(
                    test_scenario.supervisor_config.supervisor_file_path
                )
            else:
                supervisor_contract_code = test_scenario.supervisor_config.supervisor_contract
            supervisor_contract_version_id = (
                test_scenario.supervisor_config.supervisor_contract_version_id
            )
            supervisee_version_id_mapping = {
                supervisee_contract.clu_resource_id: supervisee_contract.smart_contract_version_id
                for supervisee_contract in test_scenario.supervisor_config.supervisee_contracts
                if supervisee_contract.clu_resource_id
            }
            smart_contracts.extend(test_scenario.supervisor_config.supervisee_contracts)

            supervisor_contract_config = test_scenario.supervisor_config

        elif test_scenario.contract_config:
            setup_events.extend(get_contract_setup_events(test_scenario))
            smart_contracts.append(test_scenario.contract_config)

        else:
            raise ValueError("Test scenario must have supervisor or contract config!")

        if expected_simulation_error and self.assertions_exist_in_subtests(test_scenario.sub_tests):
            raise ValueError(
                "Test scenario should not contain expectations when a simulation error is expected."
            )
        internal_accounts = test_scenario.internal_accounts or self.internal_accounts

        events, derived_param_outputs = compile_chrono_events(test_scenario, setup_events)

        contract_codes = get_contract_contents(smart_contracts)
        
        received_error: Exception | None = None
        try:
            res = self.client.simulate_smart_contract(
                start_timestamp=test_scenario.start,
                end_timestamp=test_scenario.end,
                supervisor_contract_code=supervisor_contract_code,
                supervisor_contract_version_id=supervisor_contract_version_id,
                supervisee_version_id_mapping=supervisee_version_id_mapping,
                contract_codes=contract_codes,
                smart_contract_version_ids=[
                    contract.smart_contract_version_id for contract in smart_contracts
                ],
                templates_parameters=[contract.template_params for contract in smart_contracts],
                internal_account_ids=internal_accounts,
                contract_config=test_scenario.contract_config,
                supervisor_contract_config=supervisor_contract_config,
                events=events,
                output_account_ids=[output[0] for output in derived_param_outputs],
                output_timestamps=[output[1] for output in derived_param_outputs],
                debug=test_scenario.debug,
            )
        except Exception as e:
            received_error = e
        finally:
            self.check_simulation_error(expected_simulation_error, received_error)
            # Breakout as simulation errored as expected. Do not run further assertions
            if expected_simulation_error:
                return

        actual_balances = get_balances(res)
        logs_with_timestamp = get_logs_with_timestamp(res)
        derived_parameters = get_derived_parameters(res)
        contract_notifications = get_contract_notifications(res)

        for sub_test in test_scenario.sub_tests:
            if sub_test.expected_balances_at_ts:
                self.check_balances_by_ts(
                    sub_test.expected_balances_at_ts,
                    actual_balances,
                    sub_test.description,
                )
            if sub_test.expected_schedules:
                self.check_schedule_processed(
                    sub_test.expected_schedules, res, sub_test.description
                )
            if sub_test.expected_posting_rejections:
                self.check_posting_rejections(
                    sub_test.expected_posting_rejections,
                    logs_with_timestamp,
                    sub_test.description,
                )
            if sub_test.expected_parameter_change_rejections:
                self.check_parameter_change_rejections(
                    sub_test.expected_parameter_change_rejections,
                    logs_with_timestamp,
                    sub_test.description,
                )
            if sub_test.expected_derived_parameters:
                self.check_derived_parameters(
                    sub_test.expected_derived_parameters,
                    derived_parameters,
                    sub_test.description,
                )
            if sub_test.expected_contract_notifications:
                self.check_contract_notifications(
                    sub_test.expected_contract_notifications,
                    contract_notifications,
                    sub_test.description,
                )

        return res

    def get_vault_version(self) -> Version:
        data: list[dict[str, Any]] = self.client.get_vault_version()
        version: dict[str, Any] = data[0]["version"]
        # As far as we know, major, minor, and patch are always integers.
        major: int = version["major"]
        minor: int = version["minor"]
        patch: int = version["patch"]
        label: str = version.get("label", "")
        return Version(f"{major}.{minor}.{patch}{label}")


def get_contract_contents(contract_configs: list[ContractConfig]) -> list[str]:
    return [
        contract_config.contract_content
        if contract_config.contract_content
        else load_file_contents(contract_config.contract_file_path)
        for contract_config in contract_configs
    ]


def compile_chrono_events(
    test_scenario: SimulationTestScenario, setup_events: list[SimulationEvent]
) -> tuple[list[SimulationEvent], list[tuple[str, datetime]]]:
    """
    Combines setup events with custom events from test scenario subtests.
    Sorts events chronologically.

    :param test_scenario: SimulationTestScenario
    :param setup_events: SimulationEvents generated by helper methods, e.g.
    account/plan creations or plan association events
    :returns: list of setup events + custom scenario events, and list of require derived param
     outputs as tuple of account id and datetime
    """
    previous_subtest_last_event_ts = datetime.min.replace(tzinfo=timezone.utc)
    previous_subtest_last_assertion_ts = datetime.min.replace(tzinfo=timezone.utc)
    current_subtest_first_event_ts = datetime.max.replace(tzinfo=timezone.utc)
    current_subtest_first_assertion_ts = datetime.max.replace(tzinfo=timezone.utc)
    assertion_ts = []
    events: list[SimulationEvent] = []
    derived_param_outputs: list[tuple[str, datetime]] = []

    for sub_test in test_scenario.sub_tests:
        if sub_test.events:
            current_subtest_first_event_ts = sub_test.events[0].time

            if current_subtest_first_event_ts < previous_subtest_last_event_ts:
                log.warning(
                    f'Subtest "{sub_test.description}" contains '
                    "event timestamp before the previous one."
                )

            previous_subtest_last_event_ts = sub_test.events[-1].time
            events.extend(sub_test.events)

        if sub_test.expected_balances_at_ts:
            assertion_ts.extend(sub_test.expected_balances_at_ts.keys())

        if sub_test.expected_posting_rejections:
            assertion_ts.extend(
                expected_rejection.timestamp
                for expected_rejection in sub_test.expected_posting_rejections
            )
        if sub_test.expected_parameter_change_rejections:
            assertion_ts.extend(
                expected_rejection.timestamp
                for expected_rejection in sub_test.expected_parameter_change_rejections
            )
        if sub_test.expected_schedules:
            assertion_ts.extend(
                runtime
                for expected_schedule in sub_test.expected_schedules
                for runtime in expected_schedule.run_times
            )

        if sub_test.expected_derived_parameters:
            for expected_derived_param in sub_test.expected_derived_parameters:
                assertion_ts.append(expected_derived_param.timestamp)
                derived_param_outputs.append(
                    (
                        expected_derived_param.account_id,
                        expected_derived_param.timestamp,
                    )
                )

        if assertion_ts:
            sorted_assertion_ts = sorted(assertion_ts)
            current_subtest_first_assertion_ts = sorted_assertion_ts[0]

            if current_subtest_first_assertion_ts < previous_subtest_last_assertion_ts:
                log.warning(
                    f'Subtest "{sub_test.description}" contains '
                    "assertion timestamp before the previous one."
                )

            previous_subtest_last_assertion_ts = sorted_assertion_ts[-1]
            assertion_ts.clear()

    if (
        previous_subtest_last_event_ts > test_scenario.end
        or previous_subtest_last_assertion_ts > test_scenario.end
    ):
        log.warning("last assertion or event happens outside of simulation window")

    all_events = sorted(setup_events + events, key=lambda event: event.time)

    return all_events, derived_param_outputs


def convert_sim_balance(sim_balance: dict[str, str]) -> tuple[BalanceDimensions, Balance]:
    """
    Converts a simulation balance to a BalanceDefaultDict entry.
    :param sim_balance: simulation balance to convert
    """
    return (
        BalanceDimensions(
            address=sim_balance["account_address"],
            asset=sim_balance["asset"],
            denomination=sim_balance["denomination"],
            phase=sim_balance["phase"],
        ),
        Balance(
            Decimal(sim_balance["total_credit"]),
            Decimal(sim_balance["total_debit"]),
            Decimal(sim_balance["amount"]),
        ),
    )


def get_balances(res: list[dict[str, Any]]) -> DefaultDict[str, TimeSeries]:
    """
    Returns a Balance timeseries by value_timestamp for each account
    The timeseries entries map a given datetime to a DefaultDict of BalanceDimensions to either
    Balance or a TimeSeries of Balances. The latter provides backdating support (i.e. if the view
    of the balances for a value_timestamp changes based on the event_timestamp). The caller is
    expected to know if and when their tests will have triggered backdating, set the
    `return_latest_event_timestamp` parameter accordingly and process the different return type

    WARNING: We do not support multiple events with same value and event_timestamp. Although the
    simulator may enable this, it is not reflective of real Vault behaviour as balance consistency
    constraints and timing would not allow identical insertion_timestamps

    :param res: output from simulation endpoint
    :param return_latest_event_timestamp: If False, the balance timeseries
    maps BalanceDimensions to a Timeseries of Balances. If True it maps BalanceDimensions to the
    last available Balance for the value_timestamp. Use False if you are expecting backdating and
    need to check values for a given value_timestamp at different event_timestamp values
    :return: account ids to corresponding balance timeseries
    """

    # This stores account id -> value_timestamp -> BalanceDimensions -> (event_timestamp, balance)
    account_balance_updates = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [])))
    # This stores account id -> TimeSeries -> BalanceDimensions -> Balance
    account_balance_timeseries = defaultdict(
        lambda: TimeSeries([], return_on_empty=defaultdict(lambda: Balance()))
    )

    # result data structure for balances is 'balances' -> account_id -> 'balances' -> list[balance]
    for result in res:
        result_inner = result["result"]
        for balances in result_inner["balances"].values():
            balances_inner = balances["balances"]
            for sim_balance in balances_inner:
                # results are ordered by event_timestamp so if there are multiple per
                #  value_timestamp we don't need to worry about ordering them
                event_timestamp = parser.parse(result_inner["timestamp"])
                value_timestamp = parser.parse(sim_balance["value_time"])
                dimensions, balance = convert_sim_balance(sim_balance)
                account_balance_updates[sim_balance["account_id"]][value_timestamp][
                    dimensions
                ].append((event_timestamp, balance))

    for account_id, balance_map in account_balance_updates.items():
        # By not resetting the entries for each value_timestamp, we ensure we get the most recent
        # non-default value for given dimensions
        value_timestamp_entries = []
        dimension_entries = defaultdict(lambda: Balance())

        for value_timestamp, balance_dict in balance_map.items():
            for dimensions, event_ts_balance_list in balance_dict.items():
                dimension_entries[dimensions] = event_ts_balance_list[-1][1]

            value_timestamp_entries.append((value_timestamp, deepcopy(dimension_entries)))

        account_balance_timeseries[account_id] = TimeSeries(
            value_timestamp_entries, return_on_empty=defaultdict(lambda: Balance())
        )

    return account_balance_timeseries


def get_derived_parameters(res: list[dict[str, Any]]) -> dict[str, TimeSeries]:
    """
    Returns a dictionary of derived parameters timeseries, using the account id as a key
    :param res: The response from simulation endpoint
    """

    outputs = defaultdict(lambda: [])

    for result in res:
        derived_params = result["result"]["derived_params"]
        if derived_params:
            timestamp = parser.parse(result["result"]["timestamp"])
            for account_id in derived_params:
                outputs[account_id].append((timestamp, derived_params[account_id]["values"]))

    return {k: TimeSeries(outputs[k]) for k in outputs}


def get_contract_notifications(
    res: list[dict[str, Any]],
) -> dict[str, dict[str, list[tuple[datetime, dict[str, str]]]]]:
    """
    Extract notifications from simulation response
    :param res: output from simulation endpoint
    :return: dict of resource id to notification type to list of notifications
    """

    # resource id -> notification type -> [(datetime, notification contents)]
    outputs: dict[str, dict[str, list[tuple[datetime, dict[str, str]]]]] = defaultdict(
        lambda: defaultdict(lambda: ([]))
    )

    for result in res:
        if "contract_notification_events" in result["result"]:
            timestamp = parser.parse(result["result"]["timestamp"])
            for resource_id, notifications in result["result"][
                "contract_notification_events"
            ].items():
                for notification in notifications["contract_notification_events"]:
                    outputs[resource_id][notification["notification_type"]].append(
                        (timestamp, notification)
                    )
    return outputs


def get_flag_definition_created(res: list[dict[str, Any]], flag_definition_id: str) -> bool:
    """
    Returns True if log found for create_flag_definition_event
    :param res: output from simulation endpoint
    :return: true if event found in logs
    """

    flag_definition_created_substr = f'created flag definition "{flag_definition_id}"'

    return any(_get_logs_with_substring(res, flag_definition_created_substr))


def get_flag_created(
    res: list[dict[str, Any]], flag_definition_id: str, account_id: str = MAIN_ACCOUNT
) -> bool:
    """
    Returns True if log found for create_flag_event
    :param res: output from simulation endpoint
    :param flag_definition_id: flag definition id
    :param account_id: internal or customer account id
    :return: true if event found in logs
    """

    flag_created_substr = f'"{flag_definition_id}" for account "{account_id}"'

    return any(_get_logs_with_substring(res, flag_created_substr))


def get_postings(
    res: list[dict[str, Any]],
    account_id: str = MAIN_ACCOUNT,
    balance_dimensions: BalanceDimensions | None = None,
) -> list[dict[str, Any]]:
    """
    Returns committed postings for specified account_id and balance address
    :param res: output from simulation endpoint
    :param account_id: internal or customer account id
    :param balance_dimensions: balance dimensions
    :return: committed postings
    """
    balance_dimensions = balance_dimensions or BalanceDimensions()
    pibs = (
        pibs
        for response in res
        for pibs in response["result"]["posting_instruction_batches"]
        if response["result"]["posting_instruction_batches"]
    )

    posting_instructions = (pi for pib in pibs for pi in pib["posting_instructions"])

    return [
        committed_posting
        for pi in posting_instructions
        for committed_posting in pi["committed_postings"]
        if committed_posting["account_address"] == balance_dimensions.address
        and committed_posting["account_id"] == account_id
    ]


def get_posting_instruction_batch(
    res: list[dict[str, Any]], event_type: str
) -> dict[str, TimeSeries]:
    """
    Returns a posting instruction timeseries by timestamp for each target_account_id.
    :param res: output from simulation endpoint
    :param event_type: event type
    :return: list of posting instruction events
    """
    # this stores target_account_id -> timestamp -> posting instruction records
    posting_instructions = defaultdict(lambda: defaultdict(lambda: []))
    for result in res:
        result_data = result["result"]
        event_timestamp = parser.parse(result_data["timestamp"])

        for pibs in result_data["posting_instruction_batches"]:
            for pis in pibs["posting_instructions"]:
                if event_type not in pis:
                    continue

                posting_instructions[pis[event_type]["target_account_id"]][event_timestamp].append(
                    pis[event_type]
                )

    # this stores target_account_id -> (timestamp, posting instruction records)
    posting_instructions_timeseries = defaultdict(lambda: TimeSeries([]))
    for account, timeseries in posting_instructions.items():
        posting_instructions_timeseries[account] = TimeSeries(
            [(timestamp, pi) for timestamp, pi in timeseries.items()],
            return_on_empty={},
        )

    return posting_instructions_timeseries


def get_num_postings(
    res: list[dict[str, Any]],
    account_id: str = MAIN_ACCOUNT,
    balance_dimensions: BalanceDimensions | None = None,
) -> int:
    """
    Returns number of committed postings for specified account_id and balance address
    :param res: output from simulation endpoint
    :param account_id: internal or customer account id
    :param balance_dimensions: balance dimensions
    :return: number of comitted postings
    """
    balance_dimensions = balance_dimensions or BalanceDimensions()
    return len(get_postings(res, account_id, balance_dimensions))


def get_logs(res: list[dict[str, Any]]) -> str:
    """
    Returns all logs from simulation result
    :param res: output from simulation endpoint
    :return: logs from simulation endpoint
    """

    return "; ".join(
        (log for list_of_log_lists in res for log in list_of_log_lists["result"]["logs"])
    )


def get_account_logs(res: list[dict[str, Any]], account_id: str = MAIN_ACCOUNT) -> str:
    """
    Returns logs from simulation result for a specific account_id
    :param res: output from simulation endpoint
    :param account_id: internal or customer account id
    :return: logs from simulation endpoint for specific account ID
    """
    account_substr = f'account "{account_id}"'
    return "; ".join(_get_logs_with_substring(res, account_substr))


def create_supervisor_config(
    supervisor_contract: str,
    supervisor_contract_version_id: str,
    supervisees: list[SuperviseeConfig],
    global_params: list[CreateGlobalParameterEvent] | None = None,
) -> SupervisorConfig:
    """
    Creates a SupervisorConfig object based on the parameters supplied.
    :param supervisor_contract: supervisor contract file
    :param supervisor_contract_version_id: supervisor contract version ID
    :param supervisees: list of SuperviseeConfig objects
    """
    supervisee_contracts = []
    for supervisee in supervisees:
        account_config = [
            AccountConfig(
                account_id_base=f"{supervisee.account_name} ",
                instance_params=supervisee.instance_parameters,
                number_of_accounts=supervisee.instances,
            )
        ]

        contract_config = ContractConfig(
            clu_resource_id=supervisee.contract_id,
            contract_file_path=supervisee.contract_file,
            template_params=supervisee.template_parameters,
            smart_contract_version_id=supervisee.version,
            account_configs=account_config,
            linked_contract_modules=supervisee.linked_contract_modules,
        )

        supervisee_contracts.append(contract_config)

    return SupervisorConfig(
        supervisor_file_path=supervisor_contract,
        supervisee_contracts=supervisee_contracts,
        supervisor_contract_version_id=supervisor_contract_version_id,
        global_params=global_params,
    )


def get_plan_logs(res: list[dict[str, Any]], plan_id: str) -> str:
    """
    Returns plan logs from simulation result for a specific plan id
    :param res: output from simulation endpoint
    :param plan_id: plan instruction id
    :return: plan logs
    """
    plan_substr = f'plan "{plan_id}"'
    return "; ".join(_get_logs_with_substring(res, plan_substr))


def get_plan_created(
    res: list[dict[str, Any]], plan_id: str, supervisor_version_id: str = ""
) -> bool:
    """
    Returns True if plan has been created and False if plan creation information cannot be found
    in logs
    :param res: output from simulation endpoint
    :param plan_id: plan instruction id
    :param supervisor_version_id: supervisor contract version id
    :return: True if plan creation log exists in response
    """
    plan_created = f'created plan "{plan_id}"'
    if supervisor_version_id:
        plan_created += f' for supervisor contract version "{supervisor_version_id}"'

    return any(_get_logs_with_substring(res, plan_created))


def get_plan_assoc_created(res: list[dict[str, Any]], plan_id: str, account_id: str) -> bool:
    """
    Returns True if plan association has been created and False if plan association
    information cannot be found in logs
    :param res: output from simulation endpoint
    :param plan_id: plan instruction id
    :param account_id: customer account id
    :return: True if plan association creation log exists in response
    """
    plan_assoc_created = f'created account plan association for account "{account_id}"'
    plan_assoc_created += f' and plan "{plan_id}"'

    return any(_get_logs_with_substring(res, plan_assoc_created))


def get_module_link_created(
    res: list[dict[str, Any]], aliases: list[str], smart_contract_version_id: str
) -> bool:
    """
    Returns True if contract module links have been created and False if contract module links
    information cannot be found in logs
    :param res: output from simulation endpoint
    :param module_alias: alias of the contract module
    :param account_id: customer account id
    :return: True if contract module link log exists in response
    """
    contract_module_link_created = "created smart contract module versions link with id "
    aliases_as_str = "_".join(aliases)
    contract_module_link_created += (
        f'"sim_link_modules_{aliases_as_str}_with_contract_{smart_contract_version_id}"'
    )
    return any(_get_logs_with_substring(res, contract_module_link_created))


def get_logs_with_timestamp(res: list[dict[str, Any]]) -> dict[datetime, list[str]]:
    """
    Returns all logs from simulation result with logs grouped by timestamp
    :param res: output from simulation endpoint
    :return: logs grouped by timestamp
    """

    list_of_logs = (
        {log["result"]["timestamp"]: log["result"]["logs"]} for log in res if log["result"]["logs"]
    )

    logs_with_timestamp = defaultdict(list)

    for result in list_of_logs:
        k, v = list(result.items())[0]
        logs_with_timestamp[parser.parse(k)] += v

    return logs_with_timestamp


def has_matching_processed_scheduled_event(
    logs: list[str], event_id: str, account_id: str = "", plan_id: str = ""
) -> bool:
    for_str = ""
    if account_id:
        for_str = f'for account "{account_id}"'
    elif plan_id:
        for_str = f'for plan "{plan_id}"'
    else:
        raise ValueError("account_id or plan_id must be provided")
    return f'processed scheduled event "{event_id}" {for_str}' in logs


def get_processed_scheduled_events(
    res: list[dict[str, Any]],
    event_id: str,
    account_id: str = "",
    plan_id: str = "",
) -> list[str]:
    """
    Returns a list of timestamps for processed scheduled events found for specific
    account id or plan id
    :param res: output from simulation endpoint
    :param event_id: id of the event
    :param account_id: internal or customer account id
    :param plan_id: account plan association id
    :return: list of timestamps
    """
    return [
        result["result"]["timestamp"]
        for result in res
        if has_matching_processed_scheduled_event(
            result["result"]["logs"], event_id, account_id, plan_id
        )
    ]


def print_json(print_identifier: str, json_obj: Any) -> None:
    print(
        f"{print_identifier}: "
        f"{json.dumps(json_obj, indent=4, sort_keys=True, cls=DecimalEncoder)}"
    )


def print_postings(
    res: list[dict[str, Any]],
    account_id: str = MAIN_ACCOUNT,
    balance_dimensions: BalanceDimensions | None = None,
) -> None:
    balance_dimensions = balance_dimensions or BalanceDimensions()
    postings = get_postings(res, account_id, balance_dimensions)
    print_json("Postings", postings)


def print_log(res: list[dict[str, Any]]) -> None:
    print_json("Event log", get_logs(res))


def _get_logs_with_substring(res: list[dict[str, Any]], substring: str) -> Generator:
    return (
        log
        for list_of_log_lists in res
        for log in list_of_log_lists["result"]["logs"]
        if substring in "".join(list_of_log_lists["result"]["logs"])
    )


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)
