# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime, timezone
from time import time
from typing import List
from unittest.mock import MagicMock, patch

# inception sdk
from inception_sdk.test_framework.contracts.simulation import vault_caller
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase


# this is a unit test that uses the SimulationTestCase class but mocks the loggers
# in theory this can be done with calling vault_caller.Client.simulate_smart_contract,
# but using the actual SimulationTestCase itself ensures that if the framework changes,
# the loggers are still used as long as sim tests eventually call client.simulate_smart_contract
class TestSimulationLoggers(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.load_test_config()

    def setUp(self):
        self._started_at = time()

    def tearDown(self):
        self._elapsed_time = time() - self._started_at
        # Uncomment this for timing info.
        print("{} ({}s)".format(self.id().rpartition(".")[2], round(self._elapsed_time, 2)))

    @patch.object(vault_caller, "request_logger")
    @patch.object(vault_caller, "response_logger")
    def test_simulate_smart_contract_calls_request_and_response_loggers(
        self, mock_response_logger: MagicMock, mock_request_logger: MagicMock
    ):

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        events: List = []

        self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            internal_account_ids=["1"],
        )

        # smart_contract_version_id is randomly generated for Internal Accounts,
        # cannot assert exact call args
        mock_request_logger.debug.assert_called_once()
        mock_response_logger.debug.assert_called_once()
