# standard libs
from typing import Any, Generator
from unittest import TestCase

# inception sdk
import inception_sdk.common.python.flag_utils as flag_utils
from inception_sdk.test_framework.common.config import (
    EnvironmentPurpose,
    extract_framework_environments_from_config,
)
from inception_sdk.test_framework.workflows.simulation.workflows_api_client import (
    WorkflowsApiClient,
)


class WorkflowsApiTestBase(TestCase):
    @classmethod
    def setUpClass(cls):
        flag_utils.parse_flags(allow_unknown=True)

        environment, _ = extract_framework_environments_from_config(
            environment_purpose=EnvironmentPurpose.SIM
        )
        workflow_api_url = environment.workflow_api_url
        auth_token = environment.service_account.token
        if not workflow_api_url or not auth_token:
            raise ValueError(
                "workflow_api_url and/or service_account.token not found in specified config"
            )
        cls.workflows_api_client = WorkflowsApiClient(
            base_url=workflow_api_url, auth_token=auth_token
        )

        super().setUpClass()

    def simulate_workflow(
        self,
        specification,
        events=None,
        environment_variables=None,
        instantiation_context=None,
        starting_state=None,
        auto_fire_events=None,
        check_status=True,
    ):
        response = self.workflows_api_client.simulate_workflow(
            specification=specification,
            events=events,
            environment_variables=environment_variables,
            instantiation_context=instantiation_context,
            starting_state=starting_state,
            auto_fire_events=auto_fire_events,
            check_status=check_status,
        )
        return response

    @staticmethod
    def build_expected_simulator_step(
        state: dict = None,
        triggering_event: dict = None,
        side_effect_events: list = None,
        side_effect_ticket_creations: list = None,
        side_effect_ticket_updates: list = None,
        side_effect_ticket_closures: list = None,
        side_effect_callbacks: list = None,
        side_effect_global_uis: list = None,
        side_effect_instantiations: list = None,
        side_effect_state_ui: dict = None,
        side_effect_vault_callbacks: list = None,
        side_effect_external_callbacks: list = None,
    ) -> dict:
        """
        Helper that build expected simulator response
        """
        return {
            "state": state or {},
            "triggering_event": triggering_event or {},
            "side_effect_events": side_effect_events or [],
            "side_effect_ticket_creations": side_effect_ticket_creations or [],
            "side_effect_ticket_updates": side_effect_ticket_updates or [],
            "side_effect_ticket_closures": side_effect_ticket_closures or [],
            "side_effect_callbacks": side_effect_callbacks or [],
            "side_effect_global_uis": side_effect_global_uis or [],
            "side_effect_instantiations": side_effect_instantiations or [],
            "side_effect_state_ui": side_effect_state_ui
            or {"ui_panels": [], "ui_actions": [], "ui_inputs": []},
            "side_effect_vault_callbacks": side_effect_vault_callbacks or [],
            "side_effect_external_callbacks": side_effect_external_callbacks or [],
        }

    @staticmethod
    def get_side_effects(res: dict) -> dict[str, Generator[Any, None, None]]:
        """
        Helper that takes in workflow simulation response
        And return dictionary of iterator of side effects
        """
        return {
            "events": _get_side_effect_events(res),
            "ticket_creations": _get_side_effect_ticket_creations(res),
            "callbacks": _get_side_effect_callbacks(res),
            "global_uis_panels": _get_side_effect_global_uis_panels(res),
            "instantiations": _get_side_effect_instantiations(res),
            "state_ui_panels": _get_side_effect_state_ui_panels(res),
            "state_ui_actions": _get_side_effect_state_ui_actions(res),
            "vault_callbacks": _get_side_effect_callbacks(res),
        }

    @staticmethod
    def get_next_event_name(side_effects: dict) -> str:
        """
        Helper that takes side effects with events
        And return the next event name
        """
        return next(side_effects["events"])["name"]

    @staticmethod
    def get_next_context(side_effects: dict) -> str:
        """
        Helper that takes side effect with events
        And return the next event context
        """
        return next(side_effects["events"])["context"]

    @staticmethod
    def get_next_target(side_effects: dict) -> str:
        """
        Helper that takes in side effect with callbacks
        And return the next target
        """
        return next(side_effects["callbacks"])["target"]

    @staticmethod
    def get_next_workflow_definition_id(side_effects: dict) -> str:
        """
        Helper that takes in side effect with instantiations
        And return the next workflow_definition_id
        """
        return next(side_effects["instantiations"])["workflow_definition_id"]

    @staticmethod
    def get_next_ticket_title(side_effects: dict) -> str:
        """
        Helper that takes in side effects with ticket creations
        And return the next ticket title
        """
        return next(side_effects["ticket_creations"])["title"]

    @staticmethod
    def get_next_state_ui_panel_id(side_effects: dict) -> str:
        """
        Helper that takes in side effects with state ui panels
        And return the next panel id
        """
        return next(side_effects["state_ui_panels"])["id"]

    @staticmethod
    def get_next_ui_actions_id(side_effects: dict) -> str:
        """
        Helper that takes in side effect with state ui actions
        And return the next state ui action id
        """
        return next(side_effects["state_ui_actions"])["id"]

    @staticmethod
    def get_next_ui_panel_id(side_effects: dict) -> str:
        """
        Helper that takes side effects with global ui panels
        And return the ui panel id
        """
        return next(side_effects["global_uis_panels"])["id"]


def _get_side_effect_events(res: dict) -> Generator[Any, None, None]:
    """
    Helper that takes in workflow simulation response
    And return the iteration of side effect events
    """
    side_effect_events = (
        side_effect_event
        for step in res["steps"]
        for side_effect_event in step["side_effect_events"]
    )
    return side_effect_events


def _get_side_effect_callbacks(res: dict) -> Generator[Any, None, None]:
    """
    Helper that takes in workflow simulation response
    And return the iteration of side effect callbacks
    """
    side_effect_callbacks = (
        side_effect_callback
        for step in res["steps"]
        for side_effect_callback in step["side_effect_callbacks"]
    )
    return side_effect_callbacks


def _get_side_effect_instantiations(res: dict) -> Generator[Any, None, None]:
    """
    Helper that takes in workflow simulation response
    And return the iteration of side effect instantiations
    """
    side_effect_instantiations = (
        side_effect_instantiation
        for step in res["steps"]
        for side_effect_instantiation in step["side_effect_instantiations"]
    )
    return side_effect_instantiations


def _get_side_effect_ticket_creations(res: dict) -> Generator[Any, None, None]:
    """
    Helper that takes in workflow simulation response
    And return the iterator of side effect ticket creations
    """
    side_effect_ticket_creations = (
        side_effect_ticket_creation
        for step in res["steps"]
        for side_effect_ticket_creation in step["side_effect_ticket_creations"]
    )
    return side_effect_ticket_creations


def _get_side_effect_state_ui_actions(res: dict) -> Generator[Any, None, None]:
    """
    Helper that takes in test workflow simulation response
    And return the iterator of ui actions
    """
    ui_actions = (
        ui_action
        for step in res["steps"]
        for ui_action in step["side_effect_state_ui"]["ui_actions"]
    )
    return ui_actions


def _get_side_effect_state_ui_panels(res: dict) -> Generator[Any, None, None]:
    """
    Helper that takes in workflow simulation response
    And return the iterator of side effect state_ui
    """
    side_effect_state_ui_panels = (
        ui_panel for step in res["steps"] for ui_panel in step["side_effect_state_ui"]["ui_panels"]
    )
    return side_effect_state_ui_panels


def _get_side_effect_global_uis_panels(res: dict) -> Generator[Any, None, None]:
    """
    Helper that takes in test workflow simulation response
    And return the iterator of side effect global ui panels
    """
    side_effect_global_uis_ui_panels = (
        ui_panel
        for step in res["steps"]
        for side_effect_global_ui in step["side_effect_global_uis"]
        for ui_panel in side_effect_global_ui["ui_panels"]
    )
    return side_effect_global_uis_ui_panels
