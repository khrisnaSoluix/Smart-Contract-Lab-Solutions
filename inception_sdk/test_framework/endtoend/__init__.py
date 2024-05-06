# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# flake8: noqa
# standard libs
import functools
import logging
import os
import signal
import sys
import unittest
from typing import Callable

# third party
from semantic_version import Version

# inception sdk
import inception_sdk.common.python.flag_utils as flag_utils
import inception_sdk.test_framework.endtoend as endtoend
import inception_sdk.test_framework.endtoend.accounts_helper as accounts_helper
import inception_sdk.test_framework.endtoend.balances as balances_helper
import inception_sdk.test_framework.endtoend.contract_modules_helper as contract_modules_helper
import inception_sdk.test_framework.endtoend.contracts_helper as contracts_helper
import inception_sdk.test_framework.endtoend.core_api_helper as core_api_helper
import inception_sdk.test_framework.endtoend.data_loader_helper as data_loader_helper
import inception_sdk.test_framework.endtoend.helper as helper
import inception_sdk.test_framework.endtoend.kafka_helper as kafka_helper
import inception_sdk.test_framework.endtoend.postings as postings_helper
import inception_sdk.test_framework.endtoend.schedule_helper as schedule_helper
import inception_sdk.test_framework.endtoend.supervisors_helper as supervisors_helper
import inception_sdk.test_framework.endtoend.workflows_api_helper as workflows_api_helper
import inception_sdk.test_framework.endtoend.workflows_helper as workflows_helper
from inception_sdk.test_framework.common.config import FLAGS, EnvironmentPurpose, flags
from inception_sdk.test_framework.common.utils import safe_merge_dicts

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# e2e-specific flags
flags.DEFINE_boolean(
    name="use_kafka",
    default=True,
    help="Indicates whether the framework will attempt to use kafka helpers, where available."
    " This may be forced to true for certain test types",
)

testhandle = endtoend.helper.TestInstance()


def sig_handler(sig, frame):
    endtoend.helper.teardown_test_resources()
    endtoend.helper.teardown_shared_resources()
    raise KeyboardInterrupt


signal.signal(signal.SIGINT, sig_handler)
signal.signal(signal.SIGTERM, sig_handler)


KAFKA_TOPICS = [
    postings_helper.POSTINGS_API_RESPONSE_TOPIC,
    accounts_helper.ACCOUNT_UPDATE_EVENTS_TOPIC,
    supervisors_helper.PLAN_UPDATE_EVENTS_TOPIC,
    balances_helper.ACCOUNT_BALANCE_EVENTS_TOPIC,
    contracts_helper.CONTRACT_NOTIFICATIONS_TOPIC,
]


def kafka_setup(
    topics: list[str],
    consumer_config: dict[str, str | bool | int] | None = None,
    producer_config: dict[str, str | bool | int] | None = None,
) -> None:
    try:
        if endtoend.testhandle.use_kafka != True:
            raise Exception(
                "To enable Kafka, please set the TestInstance.use_kafka flag to"
                "True. This can be done by passing the command line argument "
                "'--use_kafka'."
            )

        kafka_config = endtoend.testhandle.environment.kafka_config

        # Initialise consumers
        kafka_consumer_config = kafka_config.copy()
        kafka_consumer_config.update(consumer_config or {})
        kafka_helper.initialise_all_consumers(topics, kafka_consumer_config)

        # Initialise producer
        kafka_producer_config = kafka_config.copy()
        kafka_producer_config.update(producer_config or {})
        endtoend.testhandle.kafka_producer = endtoend.kafka_helper.initialise_producer(
            kafka_producer_config
        )

    except:
        # tearDown/tearDownClass isn't called if setUp/setUpClass fails, respectively
        endtoend.helper.teardown_shared_resources()
        raise


def standard_setup(environment_purpose: EnvironmentPurpose = EnvironmentPurpose.E2E):
    try:
        endtoend.helper.setup_environments(environment_purpose)
        endtoend.contracts_helper.create_account_schedule_tags(
            endtoend.testhandle.CONTROLLED_SCHEDULES
        )
        endtoend.contracts_helper.create_flag_definitions(testhandle.FLAG_DEFINITIONS)
        endtoend.contracts_helper.create_calendars(testhandle.CALENDARS)
        # There is a circular dependency between workflows and contracts/supervisors due to our
        # e2e id replacement approach, but we can generate the workflow definition ids before
        # uploading them
        endtoend.workflows_helper.create_workflow_definition_id_mapping()
        endtoend.contracts_helper.create_required_internal_accounts(
            testhandle.TSIDE_TO_INTERNAL_ACCOUNT_ID
        )

        # At this point we know the resource ids used in CLU references for contracts, so
        # we create a merged dictionary for CLU replacement later on. This excludes supervisors
        endtoend.testhandle.clu_reference_mappings = safe_merge_dicts(
            (
                testhandle.calendar_ids_to_e2e_ids,
                testhandle.flag_definition_id_mapping,
                testhandle.workflow_definition_id_mapping,
            )
        )
        endtoend.contracts_helper.upload_contracts(testhandle.CONTRACTS)

        # This cannot be merged with the similar step above as Core API doesn't let us provide
        # product version ids
        endtoend.testhandle.clu_reference_mappings = safe_merge_dicts(
            (
                testhandle.clu_reference_mappings,
                testhandle.contract_pid_to_uploaded_product_version_id,
            )
        )
        endtoend.supervisors_helper.upload_supervisor_contracts(
            supervisor_contracts=testhandle.SUPERVISORCONTRACTS
        )
        endtoend.contract_modules_helper.upload_contract_modules(testhandle.CONTRACT_MODULES)

        # Our CLU ids are like `offset_mortgage_supervisor_contract_version` but within our tests
        # it is much nicer to use `offset_mortgage` as the supervisor contract's id. This interim
        # step gives us implicit support for the former and the latter
        supervisor_contract_version_id_mapping = {
            supervisor_contract_name
            + "_supervisor_contract_version": supervisor_contract_version_id
            for (
                supervisor_contract_name,
                supervisor_contract_version_id,
            ) in endtoend.testhandle.supervisorcontract_name_to_id.items()
        }

        # We can now add the remaining resource ids (e.g. supervisors) for use in workflows.
        # This could be merged with the similar step above as Core API lets us provide supervisor
        # contract version ids
        endtoend.testhandle.clu_reference_mappings = safe_merge_dicts(
            (
                testhandle.clu_reference_mappings,
                supervisor_contract_version_id_mapping,
            )
        )

        endtoend.workflows_helper.update_and_upload_workflows()
        endtoend.core_api_helper.init_postings_api_client(
            client_id=postings_helper.POSTINGS_API_CLIENT_ID,
            response_topic=postings_helper.POSTINGS_API_RESPONSE_TOPIC,
        )
    except:
        # tearDown/tearDownClass isn't called if setUp/setUpClass fails, respectively
        endtoend.helper.teardown_shared_resources()
        raise


def skipForVaultVersion(callback: Callable[[Version], bool] | None = None, reason=None):
    def decorator(method):
        def inner(ref: End2Endtest):
            version: Version = core_api_helper.get_vault_version()
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


class End2Endtest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure we can see full details of assertion failures
        cls.maxDiff = None

        # we allow unknown because there may be unittest flags in argv
        flag_utils.parse_flags(allow_unknown=True)
        endtoend.testhandle.use_kafka = FLAGS.use_kafka
        standard_setup(EnvironmentPurpose.E2E)

        # These statements cannot be merged as use_kafka may have been
        # initialised elsewhere
        if endtoend.testhandle.use_kafka:
            kafka_setup(KAFKA_TOPICS)

    @classmethod
    def tearDownClass(cls):
        endtoend.helper.teardown_shared_resources()

    def setUp(self):
        log.info(f"Running test: {self._testMethodName}")

    def tearDown(self):
        endtoend.helper.teardown_test_resources()


class AcceleratedEnd2EndTest(unittest.TestCase):
    default_tags: dict[str, str]
    paused_tags: dict[str, dict[str, str]]

    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName=methodName)

    class Decorators(object):
        @classmethod
        def control_schedules(cls, schedules: dict[str, list[str]]):
            """
            Decorator that allows each test to easily define which schedules will be controlled.
            A dedicated tag will be created for each schedule, allowing them to be manipulated via
            the framework (e.g. trigger_next_schedule_job_and_wait)
            :param schedules: product name to EventType names for the schedules to control
            """

            def test_decorator(function):
                @functools.wraps(function)
                def wrapper(test, *args, **kwargs):
                    endtoend.testhandle.CONTROLLED_SCHEDULES.update(schedules)
                    function(test, *args, **kwargs)

                return wrapper

            return test_decorator

    @classmethod
    def setUpClass(cls) -> None:
        # Ensure we can see full details of assertion failures
        cls.maxDiff = None
        # we allow unknown because there may be unittest flags in argv
        flag_utils.parse_flags(allow_unknown=True)
        endtoend.testhandle.use_kafka = FLAGS.use_kafka
        # TODO: this could be improved to avoid reloading environments again when
        # the individual tests use standard_setup()
        endtoend.helper.setup_environments(EnvironmentPurpose.E2E)
        # accelerated e2e's use schedule changes, so having access to the kafka topic helps track
        # when scheduling events have completed
        if endtoend.testhandle.use_kafka:
            kafka_setup(KAFKA_TOPICS + [schedule_helper.SCHEDULER_OPERATION_EVENTS_TOPIC])

    @classmethod
    def tearDownClass(cls):
        endtoend.helper.teardown_shared_resources()

    def setUp(self):
        log.info(f"Running test: {self._testMethodName}")

    def tearDown(self) -> None:
        endtoend.helper.teardown_test_resources()


def runtests() -> None:
    # This method provides support for running e2e tests from the command line as follows
    # `python3 library/common/tests/e2e/test_adjustment_creation/test_adjustment_creation.py`
    # unknown_args will not contain any e2e framework args that could trip up unittest
    # we manually re-add the binary as unittest expects this
    unknown_args = [sys.argv[0]] + flag_utils.parse_flags()
    tests = [a for a in unknown_args[1:] if a.startswith("test")]
    if len(tests) > 0:
        for test in tests:
            # this code handles cases where we have multiple TestCase classes within a module
            for i in range(len(End2Endtest.__subclasses__())):
                module = End2Endtest.__subclasses__()[i]
                if test in dir(module):
                    unittest.main(module=module, defaultTest=test, argv=unknown_args)
    else:
        unittest.main(argv=unknown_args)
