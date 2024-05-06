# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.

# third party
import requests


class WorkflowsApiClient:
    def __init__(self, base_url, auth_token):
        self.base_url = base_url
        self.auth_token = auth_token

    def _create_endpoint_url(self, url):
        if self.base_url[-1] == "/" and url[0] == "/":
            url = url[1:]
        if self.base_url[-1] != "/" and url[0] != "/":
            url = "/" + url
        return self.base_url + url

    def post(self, url, payload, auth_token=None, check_status=True):
        auth_token = self.auth_token if auth_token is None else auth_token
        headers = {"content-type": "application/json", "X-Auth-Token": auth_token}
        response = requests.post(
            self._create_endpoint_url(url), headers=headers, json=payload, cookies=None
        )
        return response

    def simulate_workflow(
        self,
        specification: str,
        events: list | None = None,
        environment_variables: dict | None = None,
        instantiation_context: dict | None = None,
        starting_state: dict | None = None,
        auto_fire_events: list | None = None,
        check_status: bool = True,
    ):
        """
        specification - the YAML Workflow Definition specification,
            from which the instance will be created. Required.

        events - The events to simulate being sent to the instance. Optional.

        instantiation_context - The context to instantiate the Workflow Instance with.
            If both instantiation_context and starting_state are present,
            a user error will be returned. Optional.

        starting_state - The state to begin the instance simulation from.
            If both instantiation_context and starting_state are present,
            a user error will be returned. Optional.

        auto_fire_events - to make the simulator auto-fire the scheduled event,
            simulating a state that has expired.
        """

        response = self.post(
            url="/v1/workflow-instances:simulate",
            payload={
                "specification": specification,
                "events": events,
                "environment_variables": environment_variables,
                "instantiation_context": instantiation_context,
                "starting_state": starting_state,
                "auto_fire_events": auto_fire_events,
            },
            check_status=check_status,
        )
        return response.json()
