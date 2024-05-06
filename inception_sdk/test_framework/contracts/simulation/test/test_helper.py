# standard libs
from unittest import TestCase

# inception sdk
import inception_sdk.test_framework.contracts.simulation.helper as simulation_helper


class SimulationHelperTest(TestCase):
    def test_create_template_parameter_change_event(self):
        test_cases = [
            {
                "description": "given smart contract version id",
                "input": {
                    "timestamp": "2021-10-11T00:00:00Z",
                    "some_template_param": "some_value",
                    "smart_contract_version_id": "12",
                },
                "expected_event": {
                    "update_smart_contract_param": {
                        "smart_contract_version_id": "12",
                        "parameter_name": "some_template_param",
                        "new_parameter_value": "some_value",
                    }
                },
            },
            {
                "description": "default smart contract version id",
                "input": {
                    "timestamp": "2021-10-11T00:00:00Z",
                    "some_template_param": "some_value",
                },
                "expected_event": {
                    "update_smart_contract_param": {
                        "smart_contract_version_id": "0",
                        "parameter_name": "some_template_param",
                        "new_parameter_value": "some_value",
                    }
                },
            },
            {
                "description": "does not allow multiple param updates in one event",
                "input": {
                    "timestamp": "2021-10-11T00:00:00Z",
                    "some_template_param": "some_value",
                    "another_template_param": "some other value",
                },
                "expected_error": "template param update can only take in one parameter per event",
            },
        ]

        for test_case in test_cases:

            if "expected_error" in test_case:
                with self.assertRaises(ValueError) as ex:

                    simulation_helper.create_template_parameter_change_event(**test_case["input"])

                    self.assertIn(
                        test_case["expected_error"],
                        str(ex.exception),
                    )
            else:
                result = simulation_helper.create_template_parameter_change_event(
                    **test_case["input"]
                )

                self.assertEqual(
                    result.time,
                    test_case["input"]["timestamp"],
                    test_case["description"],
                )
                self.assertDictEqual(
                    result.event, test_case["expected_event"], test_case["description"]
                )
