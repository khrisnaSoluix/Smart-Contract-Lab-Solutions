# inception sdk
from inception_sdk.test_framework.workflows.simulation.workflows_api_test_base import (
    WorkflowsApiTestBase,
)


class WorkflowSimulatorTest(WorkflowsApiTestBase):
    def test_dummy_workflow(self):
        """
        Our script will test the scenario:
        The ticket is closed within two days of being created.
        """

        customer_id = "7951291909702096296"

        # an instantiation context with the key our Workflow expects
        instantiation_context = {"customer_id": customer_id}

        # this will auto-fire scheduled events
        auto_fire_events_with_state_expiry = ["AUTO_FIRE_EVENT_SCHEDULED"]

        first_simulation_response = self.simulate_workflow(
            specification=self.build_test_workflow_specification_loan_approval(customer_id),
            instantiation_context=instantiation_context,
            auto_fire_events=auto_fire_events_with_state_expiry,
        )

        # grab only the steps we care about from the first simulation response
        scenario_two_steps = {"steps": first_simulation_response["steps"][:2]}

        # grab the state object from the second step
        second_simulation_starting_state = scenario_two_steps["steps"][1]["state"]

        # the event we want to fire against the state we are starting the simulation on
        second_simulation_events = [{"name": "autotrigger_ticket_close"}]

        second_simulation_response = self.simulate_workflow(
            specification=self.build_test_workflow_specification_loan_approval(customer_id),
            starting_state=second_simulation_starting_state,
            events=second_simulation_events,
        )

        self.assertEqual(len(first_simulation_response["steps"]), 3)
        self.assertEqual(len(second_simulation_response["steps"]), 1)

    def test_transform_state(self):
        """
        Test workflow transform
        """

        customer_id = "456"
        dob = "14/03/1991"

        instantiation_context = {"input_variable": "123"}

        res = self.simulate_workflow(
            specification=self.build_test_workflow_specification(customer_id, dob),
            instantiation_context=instantiation_context,
        )
        side_effects = self.get_side_effects(res)
        next_side_effect_event = next(side_effects["events"])
        self.assertEqual(next_side_effect_event["name"], "A_to_B_2")
        self.assertEqual(next_side_effect_event["context"], {"customer_id": customer_id})

    def test_steps_action(self):
        """
        Test workflow steps action
        """

        customer_id = "456"
        dob = "14/03/1991"

        simulation_starting_state = {"name": "A_transform", "globalState": {}}

        simulation_events = [{"name": "A_to_B_1", "context": {"customer_id": customer_id}}]

        res = self.simulate_workflow(
            specification=self.build_test_workflow_specification(customer_id, dob),
            starting_state=simulation_starting_state,
            events=simulation_events,
        )

        side_effects = self.get_side_effects(res)

        self.assertEqual(
            self.get_next_target(side_effects),
            "customers.GetCustomer",
        )

    def test_child_workflow(self):
        """
        Test child workflow
        """

        customer_id = "456"
        dob = "14/03/1991"

        simulation_starting_state = {
            "name": "B_2_callback",
            "globalState": {"dob": dob},
        }

        simulation_events = [{"name": "B_to_C"}]

        res = self.simulate_workflow(
            specification=self.build_test_workflow_specification(customer_id, dob),
            starting_state=simulation_starting_state,
            events=simulation_events,
        )

        side_effects = self.get_side_effects(res)

        self.assertEqual(
            self.get_next_workflow_definition_id(side_effects),
            "A_CHILD_WORKFLOW",
        )

    def test_workflow_ticket(self):
        """
        Test workflow create ticket
        """

        customer_id = "456"
        dob = "14/03/1991"

        simulation_starting_state = {
            "name": "C_child_workflow",
            "globalState": {"dob": dob},
        }

        simulation_events = [{"name": "C_to_D"}]

        res = self.simulate_workflow(
            specification=self.build_test_workflow_specification(customer_id, dob),
            starting_state=simulation_starting_state,
            events=simulation_events,
        )

        side_effects = self.get_side_effects(res)

        self.assertEqual(
            self.get_next_ticket_title(side_effects),
            "Ticket for D",
        )

    def test_state_ui_panels(self):
        """
        Test workflow state ui panels
        """

        customer_id = "456"
        dob = "14/03/1991"

        simulation_starting_state = {
            "name": "D_create_ticket",
            "globalState": {"dob": dob},
        }

        simulation_events = [{"name": "autotrigger_ticket_close"}]

        res = self.simulate_workflow(
            specification=self.build_test_workflow_specification(customer_id, dob),
            starting_state=simulation_starting_state,
            events=simulation_events,
        )

        side_effects = self.get_side_effects(res)

        self.assertEqual(
            self.get_next_state_ui_panel_id(side_effects),
            "customer",
        )

        self.assertEqual(
            self.get_next_state_ui_panel_id(side_effects),
            "extra_details",
        )

    def test_state_ui_actions(self):
        """
        Test workflow state ui actions
        """

        customer_id = "456"
        dob = "14/03/1991"

        simulation_starting_state = {
            "name": "D_create_ticket",
            "globalState": {"dob": dob},
        }

        simulation_events = [{"name": "autotrigger_ticket_close"}]

        res = self.simulate_workflow(
            specification=self.build_test_workflow_specification(customer_id, dob),
            starting_state=simulation_starting_state,
            events=simulation_events,
        )

        side_effects = self.get_side_effects(res)

        self.assertEqual(
            self.get_next_ui_actions_id(side_effects),
            "go_to_f",
        )

    def test_global_ui(self):
        """
        Test workflow global ui
        """

        customer_id = "456"
        dob = "14/03/1991"

        simulation_starting_state = {
            "name": "E_state_ui",
            "globalState": {"dob": dob},
        }

        simulation_events = [{"name": "E_to_F"}]

        res = self.simulate_workflow(
            specification=self.build_test_workflow_specification(customer_id, dob),
            starting_state=simulation_starting_state,
            events=simulation_events,
        )

        side_effects = self.get_side_effects(res)

        self.assertEqual(
            self.get_next_ui_panel_id(side_effects),
            "a_panel_for_f",
        )

    def test_simulate_workflow_instance_pre_schema_3_0_0_expect_success(self):
        # Attempt to simulate workflow with a basic specification using
        # a schema version <3.0.0
        response = self.simulate_workflow(
            specification=self.build_basic_workflow_specification(schema_version="2.1.0"),
        )

        # Construct expected response;
        step = self.build_expected_simulator_step(
            state={"name": "A", "global_state": {}},
            triggering_event={"name": "wf_inst", "context": {}},
        )
        expected_response = {"steps": [step]}

        self.assertEqual(response, expected_response)

    def test_simulate_workflow_instance_post_schema_3_0_0_expect_success(self):
        # Attempt to simulate workflow with a basic specification using
        # a schema version >=3.0.0
        response = self.simulate_workflow(
            specification=self.build_basic_workflow_specification(schema_version="3.1.0"),
        )

        # Construct expected response;
        step = self.build_expected_simulator_step(
            state={"name": "A", "global_state": {}},
            triggering_event={"name": "wf_inst", "context": {}},
        )
        expected_response = {"steps": [step]}

        self.assertEqual(response, expected_response)

    def test_simulate_workflow_with_transform_python_pre_schema_3_0_0_expect_success(
        self,
    ):
        # Attempt to simulate workflow with a basic python transform specification
        # and a schema version <3.0.0
        response = self.simulate_workflow(
            specification=self.build_basic_workflow_specification_with_python_transform(
                schema_version="2.4.0",
            )
        )

        # Construct expected response;
        step = self.build_expected_simulator_step(
            state={"name": "A", "global_state": {}},
            triggering_event={"name": "wf_inst", "context": {}},
            side_effect_events=[
                {
                    "name": "AtoB",
                    "context": {},
                    "target_is_self": True,
                    "cron_expression": "",
                }
            ],
        )
        expected_response = {"steps": [step]}

        self.assertEqual(response, expected_response)

    def test_simulate_workflow_with_transform_python_post_schema_3_0_0_expect_error(
        self,
    ):
        # Attempt to simulate workflow with a basic Python transform specification, and a
        # schema that doesn't accept Python transforms (i.e. >=3.0.0)
        res = self.simulate_workflow(
            specification=self.build_basic_workflow_specification_with_python_transform(
                schema_version="3.1.0",
            )
        )

        side_effects = self.get_side_effects(res)

        # Ensure only a single step exists in the response:
        self.assertEqual(len(res["steps"]), 1)
        # Ensure only a single side effect event is exists in the step:
        self.assertEqual(len(res["steps"][0]["side_effect_events"]), 1)
        # Ensure that the name of this side effect event is a technical error
        self.assertEqual(self.get_next_event_name(side_effects), "technical_error")

    def test_simulate_workflow_with_transform_starlark_post_schema_3_0_0_expect_success(
        self,
    ):
        # Attempt to simulate workflow with a basic Starlark transform specification, and a
        # schema version for which they are valid (i.e. >=3.0.0)
        response = self.simulate_workflow(
            specification=self.build_basic_workflow_specification_with_starlark_transform(
                schema_version="3.2.0",
            ),
        )

        # Construct expected response;
        step = self.build_expected_simulator_step(
            state={"name": "A", "global_state": {}},
            triggering_event={"name": "wf_inst", "context": {}},
            side_effect_events=[
                {
                    "name": "AtoB",
                    "context": {},
                    "target_is_self": True,
                    "cron_expression": "",
                }
            ],
        )
        expected_response = {"steps": [step]}

        self.assertEqual(response, expected_response)

    def test_simulate_workflow_with_transform_starlark_pre_schema_3_0_0_expect_error(
        self,
    ):
        # Attempt to simulate workflow with a basic Starlark transform specification, and a
        # schema for which they are invalid (i.e. <3.0.0)
        res = self.simulate_workflow(
            specification=self.build_basic_workflow_specification_with_starlark_transform(
                schema_version="2.2.0",
            ),
        )

        side_effects = self.get_side_effects(res)

        # Ensure only a single step exists in the response:
        self.assertEqual(len(res["steps"]), 1)
        # Ensure only a single side effect evvent is exists in the step:
        self.assertEqual(len(res["steps"][0]["side_effect_events"]), 1)
        # Ensure that the name of this side effect event is a technical error
        self.assertEqual(self.get_next_event_name(side_effects), "technical_error")

    @staticmethod
    def build_basic_workflow_specification(schema_version):
        return f"""
---
name: Basic test workflow
schema_version: {schema_version}
definition_version: 1.0.0
starting_state: A
end_states:
  - B
states:
  A:
    transitions:
      - to: B
        trigger: AtoB
  B: {{}}
"""

    @staticmethod
    def build_basic_workflow_specification_with_python_transform(schema_version):
        return f"""
---
name: Simple Workflow with transform
schema_version: {schema_version}
definition_version: 1.0.0
starting_state: A
end_states:
  - B
states:
  A:
    type: transform
    transform_ref: sneaky_snake
    transitions:
      - to: B
        trigger: AtoB
  B: {{}}
transforms:
  sneaky_snake: "return 'AtoB', context"
"""

    @staticmethod
    def build_basic_workflow_specification_with_starlark_transform(schema_version):
        return f"""
---
name: Simple Workflow with transform
schema_version: {schema_version}
definition_version: 1.0.0
starting_state: A
end_states:
  - B
states:
  A:
    type: transform
    transform_ref: starry_lark
    transitions:
      - to: B
        trigger: AtoB
  B: {{}}
transforms:
  starry_lark: "a_starlark_date = calendar.monthrange(2020, 12); return ['AtoB', context]"
"""

    @staticmethod
    def build_test_workflow_specification_loan_approval(customer_id):
        return f"""
---
name: Loan Approval By Operations User
schema_version: 2.2.0
definition_version: 1.0.0
starting_state: customer_loan_request
end_states:
  - customer_loan_approved
  - customer_loan_rejected
states:
  customer_loan_request:
    entry_actions:
      create_ticket:
        title: Approve Loan Request
        description:  Customer with ID ${customer_id} requested a loan
        assigned_roles: [ops_user]
        status: open
        priority: normal
        ticket_ui:
          ui_panels:
            - panel_id: approve_loan
              display_name: Approve loan for customer with ID ${customer_id}
              json_definition:
                user:
                  customer_id: ${customer_id}
          ui_actions:
            - action_id: approve
              target_status: CLOSED
              display_name: Approve
            - action_id: reject
              target_status: CANCELLED
              display_name: Reject
    transitions:
      - to: loan_approval_request_escalated_to_high
        trigger: escalate_request_high
        auto_trigger_conditions:
          schedule_expiry:
            days: 1
        actions:
          update_ticket:
            priority: high
      - to: customer_loan_approved
        trigger: autotrigger_ticket_close
        description: Customer with ID ${customer_id} loan request approved
        auto_trigger_conditions:
          ticket_conditions:
            quantifier: all
            ticket_end_statuses: CLOSED
      - to: customer_loan_rejected
        trigger: autotrigger_ticket_cancel
        description: Customer with ID ${customer_id} loan request rejected
        auto_trigger_conditions:
          ticket_conditions:
            quantifier: all
            ticket_end_statuses: CANCELLED

  loan_approval_request_escalated_to_high:
    transitions:
      - to: loan_approval_request_escalated_to_critical
        trigger: escalate_request_critical
        auto_trigger_conditions:
          schedule_expiry:
            days: 1
        actions:
          update_ticket:
            priority: do_immediately
      - to: customer_loan_approved
        trigger: autotrigger_ticket_close
        description: Customer with ID ${customer_id} loan request approved
        auto_trigger_conditions:
          ticket_conditions:
            quantifier: all
            ticket_end_statuses: CLOSED
      - to: customer_loan_rejected
        trigger: autotrigger_ticket_cancel
        description: Customer with ID ${customer_id} loan request rejected
        auto_trigger_conditions:
          ticket_conditions:
            quantifier: all
            ticket_end_statuses: CANCELLED

  loan_approval_request_escalated_to_critical:
    transitions:
      - to: customer_loan_approved
        trigger: autotrigger_ticket_close
        description: Customer with ID ${customer_id} loan request approved
        auto_trigger_conditions:
          ticket_conditions:
            quantifier: all
            ticket_end_statuses: CLOSED
      - to: customer_loan_rejected
        trigger: autotrigger_ticket_cancel
        description: Customer with ID ${customer_id} loan request rejected
        auto_trigger_conditions:
          ticket_conditions:
            quantifier: all
            ticket_end_statuses: CANCELLED

  customer_loan_approved:
    description: Customer with ID ${customer_id} loan request was approved.

  customer_loan_rejected:
    description: Customer with ID ${customer_id} loan request was rejected.

"""

    @staticmethod
    def build_test_workflow_specification(customer_id, dob):
        return f"""
---
name: Workflow for simulator-responses test for workflow_writer persona
instance_title: Test instance
description: Testing workflow
schema_version: 2.1.0
definition_version: 1.1.9
starting_state: A_transform
end_states:
  - state: F_global_ui
    result: SUCCESSFUL
states:
  A_transform:
    type: transform
    transform: |
      if context["input_variable"] == "one":
        return 'A_to_B_1', {{"customer_id": "123"}}
      else:
        return 'A_to_B_2', {{"customer_id": "456"}}
    transitions:
      - to: B_1_callback
        trigger: A_to_B_1
      - to: B_2_callback
        trigger: A_to_B_2
  B_1_callback:
    entry_actions:
      callback:
        executor: core_api
        target: customers.GetCustomer
        arguments:
          id: ${customer_id}
        response_event: B_to_C
        response_fields:
          - key_name: dob
            response_json_path: customer_details.dob
    transitions:
      - to: C_child_workflow
        trigger: B_1_to_C
        actions:
          save_to_global_state:
            context_keys:
              - dob
  B_2_callback:
    entry_actions:
      callback:
        executor: core_api
        target: customers.GetCustomer
        arguments:
          id: ${customer_id}
        response_event: B_2_to_C
        response_fields:
          - key_name: dob
            response_json_path: customer_details.dob
    transitions:
      - to: C_child_workflow
        trigger: B_to_C
        actions:
          save_to_global_state:
            context_keys:
              - dob
  C_child_workflow:
    entry_actions:
      create_child_workflow_instances:
        - definition_id: A_CHILD_WORKFLOW
          definition_version: "2.1.0"
          child_context:
            dob: ${dob}
    transitions:
      - to: D_create_ticket
        trigger: C_to_D
        auto_trigger_conditions:
          children_end_states:
            - C_to_D
  D_create_ticket:
    entry_actions:
      create_ticket:
        title: Ticket for D
        assigned_roles: [ops_user]
        ticket_ui:
          ui_inputs:
            - key: resolve_message
              string_input:
                min_length: 10
              optional: false
              display_name: close
              json_definition:
                text:
                  multiline: true
          ui_actions:
            - action_id: close
              target_status: CLOSED
              display_name: Close this ticket
              ui_inputs:
                - key: resolve_message
                  string_input:
                    min_length: 90
                  optional: false
                  display_name: close
                  json_definition:
                    text:
                      multiline: true
            - action_id: cancel
              target_status: CANCELLED
              display_name: Cancel this ticket
    transitions:
      - to: E_state_ui
        trigger: autotrigger_ticket_close
        auto_trigger_conditions:
          ticket_conditions:
            ticket_end_statuses: CLOSED
  E_state_ui:
    state_ui:
      ui_actions:
        - action_id: go_to_f
          event: E_to_F
          display_name: Transition to F
      ui_panels:
        - panel_id: customer
          display_name: The customer
          json_definition:
            customer:
              customer_id: ${dob}
        - panel_id: extra_details
          display_name: Extra details
          json_definition:
            key_value_table:
              items:
                Some label: ${dob}
                Some other label: Some static text
    transitions:
      - to: F_global_ui
        trigger: E_to_F
  F_global_ui:
    entry_actions:
      add_or_replace_global_ui_panels:
        - panel_id: a_panel_for_f
          display_name: A panel for F
          json_definition:
            key_value_table:
              items:
                Some label: ${dob}
                Some other label: Some static text
"""
