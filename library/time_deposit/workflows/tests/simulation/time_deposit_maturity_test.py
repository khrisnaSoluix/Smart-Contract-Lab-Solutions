# Standard Libs
from concurrent.futures import ThreadPoolExecutor
import json
from typing import Any, Callable, Dict

# Common
from inception_sdk.common.python.file_utils import load_file_contents
from inception_sdk.test_framework.workflows.simulation.workflows_api_test_base import (
    WorkflowsApiTestBase,
)

TIME_DEPOSIT_MATURITY_WF = "library/time_deposit/workflows/time_deposit_maturity.yaml"


class TimeDepositMaturityTest(WorkflowsApiTestBase):
    @classmethod
    def setUpClass(cls):
        cls.time_deposit_maturity_wf = load_file_contents(TIME_DEPOSIT_MATURITY_WF)
        super().setUpClass()

    def transition_event_assertion_logic(
        self, result: Dict[str, Any], expected_result: str, test_description: str
    ):
        actual_transition_event = result["steps"][0]["side_effect_events"][0]["name"]
        self.assertEqual(expected_result, actual_transition_event, "test: " + test_description)

    def run_transform_test(
        self,
        starting_state: str,
        test_description: str,
        context: Dict[str, str],
        triggering_event: str,
        expected_result: str,
        assertion_logic: Callable,
    ) -> None:

        events = [
            {
                "name": triggering_event,
                "context": context,
            },
        ]

        result = self.simulate_workflow(
            specification=self.time_deposit_maturity_wf,
            starting_state={
                "name": starting_state,
            },
            events=events,
        )
        assertion_logic(result, expected_result, test_description)

    def submit_tests(
        self,
        starting_state: str,
        triggering_event: str,
        test_cases: dict,
        assertion_logic: Callable,
    ):

        with ThreadPoolExecutor(max_workers=len(test_cases)) as executor:
            for test_case in test_cases:
                executor.submit(
                    self.run_transform_test(
                        starting_state=starting_state,
                        context=test_case["context"],
                        test_description=test_case["description"],
                        triggering_event=triggering_event,
                        expected_result=test_case["expected_transition_event"],
                        assertion_logic=assertion_logic,
                    ),
                )

    def test_time_deposit_capitalised_interest_check(self):

        test_cases = [
            {
                "description": "capitalised interest recheck",
                "context": {
                    "capitalised_interest_balances": json.dumps(["1"]),
                    "available_balance": "0",
                    "balance_check_counter": "1",
                    "account_id": "1",
                    "next_page_token": "some_token",
                },
                "expected_transition_event": "positive_capitalised_interest",
            },
            {
                "description": "no available interest",
                "context": {
                    "capitalised_interest_balances": json.dumps(["0"]),
                    "available_balance": "0",
                    "balance_check_counter": "1",
                    "account_id": "1",
                    "next_page_token": "some_token",
                },
                "expected_transition_event": "no_capitalised_interest",
            },
            {
                "description": "balance recheck counter excedeed",
                "context": {
                    "capitalised_interest_balances": json.dumps(["1"]),
                    "available_balance": "0",
                    "balance_check_counter": "20",
                    "account_id": "1",
                    "next_page_token": "some_token",
                },
                "expected_transition_event": "capitalised_interest_stuck",
            },
        ]

        self.submit_tests(
            starting_state="check_require_disbursement",
            triggering_event="no_disbursement_required",
            test_cases=test_cases,
            assertion_logic=self.transition_event_assertion_logic,
        )
