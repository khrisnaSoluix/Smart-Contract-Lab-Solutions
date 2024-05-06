# standard libs
from copy import deepcopy
from unittest import TestCase
from unittest.mock import Mock, mock_open, patch

# third party
import yaml

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
import inception_sdk.test_framework.endtoend.workflows_api_helper as workflows_api_helper
import inception_sdk.test_framework.endtoend.workflows_helper as workflows_helper

# This definition is not really valid, but contains the states we need to test
WORKFLOW_DEFINITION = """
---
name: Name
instance_title: Title
description: Description
schema_version: 2.3.0
definition_version: 2.3.4
starting_state: check_if_new_customer
end_states:
  - state: account_opened_successfully
    result: SUCCESSFUL
  - state: account_application_rejected
    result: FAILED

states:
  child_workflow_state:
    entry_actions:
      instantiate_workflow:
        definition_id: APPLY_FOR_EASY_ACCESS_SAVER
        definition_version: 1.8.0

  plan_state:
    state_name: create_plan
    entry_actions:
      vault_callback:
        arguments:
          plan:
            supervisor_contract_version_id: '&{offset_mortgage_supervisor_contract_version}'

  calendar_state:
    entry_actions:
      vault_callback:
        arguments:
          calendar_ids:
            - "&{BACS}"

  flag_state:
    flag:
      flag_definition_id: "&{ACCOUNT_DELINQUENT}"
      flagDefinitionId: "&{ACCOUNT_DELINQUENT2}"
    new_key_value_pairs:
      failure_message: "&{ACCOUNT_DELINQUENT3}"
    transform: return ["&{ACCOUNT_DELINQUENT4}", {}]

  product_state:
    entry_actions:
      vault_callback:
        arguments:
          account:
            product_id: us_checking_account

  internal_account_state:
    entry_actions:
      vault_callback:
        arguments:
          posting_instruction_batch:
            posting_instructions:
              - outbound_hard_settlement:
                  internal_account_id: "1"
"""


class WorkflowHelperTest(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_definition = yaml.safe_load(WORKFLOW_DEFINITION)

    def setUp(self) -> None:
        self.definition = deepcopy(self.base_definition)

    def test_replace_calendar_ids(
        self,
    ):
        new_definition = workflows_helper.replace_clu_syntax_resource_in_workflows(
            WORKFLOW_DEFINITION,
            {"BACS": "E2E_BACS_ID"},
        )
        yaml_definition = yaml.safe_load(new_definition)
        create_calendar = yaml_definition["states"]["calendar_state"]["entry_actions"][
            "vault_callback"
        ]["arguments"]
        self.assertEqual(create_calendar["calendar_ids"], ["E2E_BACS_ID"])

    def test_replace_child_workflow_definition_ids(
        self,
    ):
        new_definition = workflows_helper.replace_child_workflow_definition_ids(
            self.definition,
            workflow_definition_id_mapping={"APPLY_FOR_EASY_ACCESS_SAVER": "E2E_WF_ID"},
        )
        workflow_instantiation = new_definition["states"]["child_workflow_state"]["entry_actions"][
            "instantiate_workflow"
        ]
        self.assertEqual(workflow_instantiation["definition_id"], "E2E_WF_ID")
        self.assertEqual(workflow_instantiation["definition_version"], "1.0.0")

    def test_replace_internal_account_ids(
        self,
    ):
        new_definition = workflows_helper.replace_internal_account_ids(
            self.definition,
            internal_account_id_to_uploaded_id={"1": "E2E_1"},
        )
        posting_instruction_batch = new_definition["states"]["internal_account_state"][
            "entry_actions"
        ]["vault_callback"]["arguments"]["posting_instruction_batch"]
        self.assertEqual(
            posting_instruction_batch["posting_instructions"][0]["outbound_hard_settlement"][
                "internal_account_id"
            ],
            "E2E_1",
        )

    def test_replace_product_ids(
        self,
    ):
        new_definition = workflows_helper.replace_product_ids(
            self.definition,
            contract_pid_to_uploaded_pid={"us_checking_account": "E2E_us_checking_account"},
        )
        product_id = new_definition["states"]["product_state"]["entry_actions"]["vault_callback"][
            "arguments"
        ]["account"]["product_id"]
        self.assertEqual(
            product_id,
            "E2E_us_checking_account",
        )

    def test_replace_supervisor_contract_version_ids(
        self,
    ):
        new_definition = workflows_helper.replace_clu_syntax_resource_in_workflows(
            WORKFLOW_DEFINITION,
            {"offset_mortgage": "BwrqXkvhfS"},
            "_supervisor_contract_version",
        )
        yaml_definition = yaml.safe_load(new_definition)
        product_id = yaml_definition["states"]["plan_state"]["entry_actions"]["vault_callback"][
            "arguments"
        ]["plan"]["supervisor_contract_version_id"]
        self.assertEqual(
            product_id,
            "BwrqXkvhfS",
        )

    @patch.object(workflows_api_helper, "get_workflow_instances")
    @patch.object(workflows_api_helper, "batch_get_workflow_instances")
    @patch.object(workflows_api_helper, "get_workflow_definition_version")
    def test_get_child_workflow_id_retries_until_new_child_found_or_fails_gracefully(
        self,
        mock_get_workflow_definition_version: Mock,
        mock_batch_get_workflow_instances: Mock,
        mock_get_workflow_instances: Mock,
    ):
        """INC-5279"""
        wf_id = "123456789"
        wf_def_id = "sample_wf_def_id"
        wf_def_version_id = f"1.0.0,{wf_def_id}"
        parent_instance_id = "parent_instance_id"

        # Pass in only the existing child workflows value=
        mock_get_workflow_instances.return_value = [
            {"id": wf_id, "workflow_definition_id": wf_def_id}
        ]
        mock_batch_get_workflow_instances.return_value = {
            parent_instance_id: {
                "workflow_definition_id": wf_def_id,
                "workflow_definition_version_id": wf_def_version_id,
            }
        }
        mock_get_workflow_definition_version.return_value = {
            "states": [
                {
                    "name": "sample_state",
                    "spawns_children": "True",
                    "child_workflow_definition_version_ids": [wf_def_version_id],
                }
            ]
        }

        # If there are no new instantiated child workflow, but there's an old one existing,
        # the retry_call will keep retrying until failing gracefully
        with self.assertRaises(ValueError) as e:
            workflows_helper.get_child_workflow_id(
                parent_instance_id="parent_instance_id",
                parent_state_name="sample_state",
                wait_for_parent_state=False,
                existing_instantiated_child_workflows=[wf_id],
            )
        self.assertIn("Wrapped result", str(e.exception))
        self.assertIn("does not match True.", str(e.exception))
        self.assertIn(
            f"Original result: {[{'id': wf_id, 'workflow_definition_id': wf_def_id}]}",
            str(e.exception),
        )

        wf_id_2 = "987654321"
        # Now pass in a second (new) child workflows value, we are expecting success
        mock_get_workflow_instances.return_value = [
            {"id": wf_id, "workflow_definition_id": wf_def_id},
            {"id": wf_id_2, "workflow_definition_id": wf_def_id},
        ]
        real_wf_id = workflows_helper.get_child_workflow_id(
            parent_instance_id="parent_instance_id",
            parent_state_name="sample_state",
            wait_for_parent_state=False,
            existing_instantiated_child_workflows=[wf_id],
        )

        self.assertEquals(wf_id_2, real_wf_id)

        # Now try with no existing child workflows, we are expecting the method to still succeed
        mock_get_workflow_instances.return_value = [
            {"id": wf_id_2, "workflow_definition_id": wf_def_id}
        ]
        real_wf_id = workflows_helper.get_child_workflow_id(
            parent_instance_id="parent_instance_id",
            parent_state_name="sample_state",
            wait_for_parent_state=False,
            existing_instantiated_child_workflows=[],
        )

        self.assertEquals(wf_id_2, real_wf_id)

    def test_replace_flag_definition_ids(
        self,
    ):
        new_definition = workflows_helper.replace_clu_syntax_resource_in_workflows(
            WORKFLOW_DEFINITION,
            {
                "ACCOUNT_DELINQUENT": "E2E_ACCOUNT_DELINQUENT",
                "ACCOUNT_DELINQUENT2": "E2E_ACCOUNT_DELINQUENT2",
                "ACCOUNT_DELINQUENT3": "E2E_ACCOUNT_DELINQUENT3",
                "ACCOUNT_DELINQUENT4": "E2E_ACCOUNT_DELINQUENT4",
            },
        )
        yaml_definition = yaml.safe_load(new_definition)
        flag1_id = yaml_definition["states"]["flag_state"]["flag"]["flag_definition_id"]
        flag2_id = yaml_definition["states"]["flag_state"]["flag"]["flagDefinitionId"]
        flag3_id = yaml_definition["states"]["flag_state"]["new_key_value_pairs"]["failure_message"]
        flag4_id = yaml_definition["states"]["flag_state"]["transform"]
        self.assertEqual(
            flag1_id,
            "E2E_ACCOUNT_DELINQUENT",
        )
        self.assertEqual(
            flag2_id,
            "E2E_ACCOUNT_DELINQUENT2",
        )
        self.assertEqual(
            flag3_id,
            "E2E_ACCOUNT_DELINQUENT3",
        )
        self.assertEqual(
            flag4_id,
            'return ["E2E_ACCOUNT_DELINQUENT4", {}]',
        )


class UpdateWorkflowHelperTest(TestCase):
    @classmethod
    @patch.dict(endtoend.testhandle.WORKFLOWS, {"TEST_WORKFLOW": "DUMMY_PATH"})
    @patch.dict(
        endtoend.testhandle.workflow_definition_id_mapping,
        {
            "TEST_WORKFLOW": "E2E_TEST_WORKFLOW",
            "APPLY_FOR_EASY_ACCESS_SAVER": "E2E_APPLY_FOR_EASY_ACCESS_SAVER",
        },
    )
    @patch.dict(
        endtoend.testhandle.clu_reference_mappings,
        {
            # Calendar Id
            "BACS": "E2E_BACS_ID",
            # Flag Definition Id
            "ACCOUNT_DELINQUENT": "E2E_ACCOUNT_DELINQUENT",
            "ACCOUNT_DELINQUENT2": "E2E_ACCOUNT_DELINQUENT2",
            "ACCOUNT_DELINQUENT3": "E2E_ACCOUNT_DELINQUENT3",
            "ACCOUNT_DELINQUENT4": "E2E_ACCOUNT_DELINQUENT4",
            # Supervisor Id
            "offset_mortgage_supervisor_contract_version": "e2e_supervisor_contract_version",
        },
    )
    @patch("builtins.open", mock_open(read_data=WORKFLOW_DEFINITION))
    @patch.object(workflows_helper, "upload_workflow")
    def setUpClass(cls, upload_workflow_mock: Mock) -> None:
        cls.upload_workflow_mock = upload_workflow_mock
        workflows_helper.update_and_upload_workflows()
        cls.updated_definition = yaml.safe_load(upload_workflow_mock.call_args_list[0].args[1])

    def test_replace_calendar_ids(self):
        create_calendar = self.updated_definition["states"]["calendar_state"]["entry_actions"][
            "vault_callback"
        ]["arguments"]
        self.assertEqual(create_calendar["calendar_ids"], ["E2E_BACS_ID"])

    def test_replace_supervisor_contract_version_ids(
        self,
    ):
        product_id = self.updated_definition["states"]["plan_state"]["entry_actions"][
            "vault_callback"
        ]["arguments"]["plan"]["supervisor_contract_version_id"]
        self.assertEqual(
            product_id,
            "e2e_supervisor_contract_version",
        )

    def test_replace_flag_definition_ids(
        self,
    ):
        yaml_definition = self.updated_definition
        flag1_id = yaml_definition["states"]["flag_state"]["flag"]["flag_definition_id"]
        flag2_id = yaml_definition["states"]["flag_state"]["flag"]["flagDefinitionId"]
        flag3_id = yaml_definition["states"]["flag_state"]["new_key_value_pairs"]["failure_message"]
        flag4_id = yaml_definition["states"]["flag_state"]["transform"]
        self.assertEqual(
            flag1_id,
            "E2E_ACCOUNT_DELINQUENT",
        )
        self.assertEqual(
            flag2_id,
            "E2E_ACCOUNT_DELINQUENT2",
        )
        self.assertEqual(
            flag3_id,
            "E2E_ACCOUNT_DELINQUENT3",
        )
        self.assertEqual(
            flag4_id,
            'return ["E2E_ACCOUNT_DELINQUENT4", {}]',
        )
