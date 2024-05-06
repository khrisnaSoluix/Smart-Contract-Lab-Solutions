# Standard Libs
from concurrent.futures import ThreadPoolExecutor

# Common
from inception_sdk.common.python.file_utils import load_file_contents
from inception_sdk.test_framework.workflows.simulation.workflows_api_test_base import (
    WorkflowsApiTestBase,
)

APPLICATION_WF = "library/loan/workflows/loan_application.yaml"


class LoanApplicationTest(WorkflowsApiTestBase):
    @classmethod
    def setUpClass(cls):
        cls.loan_application_workflow = load_file_contents(APPLICATION_WF)
        super().setUpClass()

    def _run_validate_balloon_payment_transform(
        self,
        starting_state: str,
        description: str,
        context: dict,
        triggering_event: str,
        expected_transition_event: str,
    ) -> None:

        events = [
            {
                "name": triggering_event,
                "context": context,
            },
        ]

        res = self.simulate_workflow(
            specification=self.loan_application_workflow,
            starting_state={
                "name": starting_state,
            },
            events=events,
        )

        actual_transition_event = res["steps"][0]["side_effect_events"][0]["name"]
        self.assertEqual(expected_transition_event, actual_transition_event, "test: " + description)

    def _submit_tests(
        self,
        starting_state: str,
        triggering_event: str,
        test_cases: dict,
    ):
        with ThreadPoolExecutor(max_workers=len(test_cases)) as executor:
            for test_case in test_cases:
                executor.submit(
                    self._run_validate_balloon_payment_transform(
                        starting_state=starting_state,
                        context=test_case["context"],
                        description=test_case["description"],
                        triggering_event=triggering_event,
                        expected_transition_event=test_case["expected_transition_event"],
                    ),
                )

    def test_validate_loan_details(self):

        test_cases = [
            {
                "description": "balloon payment min repayment",
                "context": {
                    "loan_start_date": "2021-11-15",
                    "total_term": "12",
                    "repayment_day": "1",
                    "fixed_interest_loan": "True",
                    "principal": "10000",
                    "max_principal": "11000",
                    "min_principal": "5000",
                    "principal_step": "1000",
                    "max_total_term": "13",
                    "min_total_term": "10",
                    "amortisation_method": "minimum_repayment_with_balloon_payment",
                },
                "expected_transition_event": "balloon_payment_min_repayment",
            },
            {
                "description": "balloon payment interest only repayment",
                "context": {
                    "loan_start_date": "2021-11-15",
                    "total_term": "12",
                    "repayment_day": "1",
                    "fixed_interest_loan": "True",
                    "principal": "10000",
                    "max_principal": "11000",
                    "min_principal": "5000",
                    "principal_step": "1000",
                    "max_total_term": "13",
                    "min_total_term": "10",
                    "amortisation_method": "interest_only",
                },
                "expected_transition_event": "balloon_payment_interest_only_repayment",
            },
            {
                "description": "balloon payment no repayment or not a balloon payment",
                "context": {
                    "loan_start_date": "2021-11-15",
                    "total_term": "12",
                    "repayment_day": "1",
                    "fixed_interest_loan": "True",
                    "principal": "10000",
                    "max_principal": "11000",
                    "min_principal": "5000",
                    "principal_step": "1000",
                    "max_total_term": "13",
                    "min_total_term": "10",
                    "amortisation_method": "no_repayment",
                },
                "expected_transition_event": "balloon_payment_no_repayment_or_no_balloon",
            },
            {
                "description": "balloon payment invalid loan details",
                "context": {
                    "loan_start_date": "2021-11-15",
                    "total_term": "12",
                    "repayment_day": "1",
                    "fixed_interest_loan": "True",
                    "principal": "10000",
                    "max_principal": "9000",
                    "min_principal": "5000",
                    "principal_step": "1000",
                    "max_total_term": "13",
                    "min_total_term": "10",
                    "amortisation_method": "no_repayment",
                },
                "expected_transition_event": "not_eligible",
            },
        ]

        self._submit_tests(
            starting_state="choose_loan_parameters_no_repayment",
            triggering_event="loan_parameters_chosen",
            test_cases=test_cases,
        )

    def test_balloon_payment_date_computation_transform(self):

        test_cases = [
            {
                "description": "balloon date computation from last repayment date",
                "context": {
                    "loan_start_date": "2021-11-15",
                    "total_term": "12",
                    "repayment_day": "1",
                    "last_repayment_day": "2022-11-15",
                    "balloon_payment_days": "5",
                    "balloon_payment_type": "chosen_balloon_amount",
                },
                "expected_transition_event": "balloon_payment_date_obtained",
            }
        ]

        self._submit_tests(
            starting_state="choose_balloon_payment_date",
            triggering_event="balloon_date_selected",
            test_cases=test_cases,
        )
