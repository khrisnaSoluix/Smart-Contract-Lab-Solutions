# Standard Libs
from concurrent.futures import ThreadPoolExecutor
import json
from typing import Any, Callable, Dict

# Common
from inception_sdk.common.python.file_utils import load_file_contents
from inception_sdk.test_framework.workflows.simulation.workflows_api_test_base import (
    WorkflowsApiTestBase,
)

REPAYMENT_HOLIDAY_APPLICATION_WF = "library/loan/workflows/loan_repayment_holiday_application.yaml"


class LoanRepaymentHolidayApplicationTest(WorkflowsApiTestBase):
    @classmethod
    def setUpClass(cls):
        cls.loan_repayment_holiday_application_workflow = load_file_contents(
            REPAYMENT_HOLIDAY_APPLICATION_WF
        )
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
            specification=self.loan_repayment_holiday_application_workflow,
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

    def test_extract_current_parameter_details_transform(self):

        test_cases = [
            {
                "description": "no product versions or next page token",
                "context": {
                    "product_versions": "[]",
                    "product_version_id": "1234",
                    "next_page_token": "",
                },
                "expected_transition_event": "no_valid_contract",
            },
            {
                "description": "no product versions with next page token",
                "context": {
                    "product_versions": "[]",
                    "product_version_id": "1234",
                    "next_page_token": "some_token",
                },
                "expected_transition_event": "matching_product_version_not_found",
            },
            {
                "description": "non-matching product versions, with next page token",
                "context": {
                    "product_versions": json.dumps(
                        [
                            {
                                "id": "12270",
                                "display_name": "test",
                            },
                            {
                                "id": "12271",
                                "display_name": "test",
                            },
                            {
                                "id": "12272",
                                "display_name": "test",
                            },
                        ]
                    ),
                    "product_version_id": "1234",
                    "next_page_token": "some_token",
                },
                "expected_transition_event": "matching_product_version_not_found",
            },
            {
                "description": "non-matching product versions, with no page token",
                "context": {
                    "product_versions": json.dumps(
                        [
                            {
                                "id": "12270",
                                "display_name": "test",
                            },
                            {
                                "id": "12271",
                                "display_name": "test",
                            },
                            {
                                "id": "12272",
                                "display_name": "test",
                            },
                        ]
                    ),
                    "product_version_id": "1234",
                    "next_page_token": "",
                },
                "expected_transition_event": "no_valid_contract",
            },
            {
                "description": "matching product version",
                "context": {
                    "product_versions": json.dumps(
                        [
                            {
                                "id": "12270",
                                "display_name": "test",
                            },
                            {
                                "id": "12271",
                                "display_name": "test",
                            },
                            {
                                "id": "1234",
                                "display_name": "test",
                                "params": [
                                    {"name": "param_1", "value": "value_1"},
                                    {"name": "param_2", "value": "value_2"},
                                    {
                                        "name": "amortisation_method",
                                        "value": "amortisation_method_value",
                                    },
                                ],
                            },
                        ]
                    ),
                    "product_version_id": "1234",
                    "next_page_token": "some_token",
                },
                "expected_transition_event": "amortisation_method_extracted",
            },
        ]

        self.submit_tests(
            starting_state="query_contract_parameters",
            triggering_event="contract_versions_returned",
            test_cases=test_cases,
            assertion_logic=self.transition_event_assertion_logic,
        )

    def test_validate_if_balloon_payment_loan_transform(self):

        test_cases = [
            {
                "description": "interest only amortisation method",
                "context": {
                    "amortisation_method": "interest_only",
                },
                "expected_transition_event": "is_balloon_loan",
            },
            {
                "description": "no repayment amortisation method",
                "context": {
                    "amortisation_method": "no_repayment",
                },
                "expected_transition_event": "is_balloon_loan",
            },
            {
                "description": "minimum repayment amortisation method",
                "context": {
                    "amortisation_method": "minimum_repayment_with_balloon_payment",
                },
                "expected_transition_event": "is_balloon_loan",
            },
            {
                "description": "declining principal amortisation method",
                "context": {
                    "amortisation_method": "declining_principal",
                },
                "expected_transition_event": "not_balloon_loan",
            },
        ]

        self.submit_tests(
            starting_state="extract_current_parameter_details",
            triggering_event="amortisation_method_extracted",
            test_cases=test_cases,
            assertion_logic=self.transition_event_assertion_logic,
        )
