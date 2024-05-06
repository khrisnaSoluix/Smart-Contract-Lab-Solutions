# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import functools
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any

# third party
import requests

# inception sdk
from inception_sdk.common.python.file_utils import load_file_contents
from inception_sdk.test_framework.common.utils import replace_clu_dependencies
from inception_sdk.test_framework.contracts.files import (
    EMPTY_ASSET_CONTRACT,
    EMPTY_LIABILITY_CONTRACT,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    ContractConfig,
    ContractModuleConfig,
    SimulationEvent,
    SupervisorConfig,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    account_to_simulate,
    create_derived_parameters_instructions,
    create_flag_definition_event,
    create_smart_contract_module_versions_link,
)

request_logger = logging.getLogger(".".join([__name__, "sim_test_request_logger"]))
response_logger = logging.getLogger(".".join([__name__, "sim_test_response_logger"]))
request_logger.setLevel(os.environ.get("LOGLEVEL", "INFO"))
response_logger.setLevel(os.environ.get("LOGLEVEL", "INFO"))


_DEFAULT_OPS_AUTH_HEADER_NAME = "tm_ops_auth_token"


class AuthCookieNotFound(Exception):
    def __str__(self):
        return "Could not find the auth cookie with key %r" % self.args[0]


class VaultException(Exception):
    def __init__(self, vault_error_code, message):
        self.vault_error_code = vault_error_code
        self.message = message

    def __str__(self):
        return "An exception was raised inside Vault:\nError Code: %s\nMessage:\n%s" % (
            self.vault_error_code,
            self.message,
        )


def _auth_required(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)

    return wrapper


class Client:
    def __init__(self, *, core_api_url, auth_token, ops_auth_header_name=None):
        self._core_api_url = core_api_url.rstrip("/")
        self._auth_token = auth_token
        self._ops_auth_header_name = ops_auth_header_name or _DEFAULT_OPS_AUTH_HEADER_NAME
        self._session = requests.Session()
        self._set_session_headers()

    @_auth_required
    def _api_get(
        self, url: str, params: dict[str, Any], timeout: str, debug=False
    ) -> list[dict[str, Any]]:
        response: requests.Response = self._session.get(
            url=self._core_api_url + url,
            params=params,
            headers={"grpc-timeout": timeout},
            stream=debug,
        )
        return self._handle_response(response, debug)

    @_auth_required
    def _api_post(
        self, url: str, payload: dict[str, Any], timeout: str, debug=False
    ) -> list[dict[str, Any]]:
        response: requests.Response = self._session.post(
            self._core_api_url + url,
            headers={"grpc-timeout": timeout},
            json=payload,
            stream=debug,
        )
        request_logger.debug(json.dumps(payload))
        return self._handle_response(response, debug)

    def _handle_response(self, response: requests.Response, debug=False) -> list[dict[str, Any]]:
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            return self._handle_error(response, e)

        try:
            data = []
            # The response for this endpoint is streamed as new line separated JSON.
            for line in response.iter_lines():
                line_json = json.loads(line)
                data.append(line_json)
                response_logger.debug(json.dumps(line_json))
                if line_json.get("error"):
                    return self._raise_error(line)
            return data
        except requests.exceptions.HTTPError as e:
            return self._handle_error(response, e)

    @staticmethod
    def _handle_error(response, e):
        try:
            content = json.loads(response.text)
        except json.decoder.JSONDecodeError as json_e:
            raise json_e from e

        if "vault_error_code" in content and "message" in content:
            raise VaultException(content["vault_error_code"], content["message"]) from e

        if "error" in content:
            raise ValueError(content["error"]) from e

        raise e

    @staticmethod
    def _raise_error(response):
        try:
            content = json.loads(response)
        except json.decoder.JSONDecodeError as json_e:
            raise json_e

        if "error" in content:
            raise ValueError(content["error"])

    def _set_session_headers(self):
        headers = {"X-Auth-Token": self._auth_token, "Content-Type": "application/json"}
        self._session.headers = headers

    def get_vault_version(self) -> requests.Response:
        response = self._api_get("/v1/vault-version", None, None)
        return response

    def simulate_smart_contract(
        self,
        start_timestamp: datetime,
        end_timestamp: datetime,
        events: list[SimulationEvent],
        timeout: str = "360S",
        supervisor_contract_code: str | None = None,
        supervisor_contract_version_id: str | None = None,
        supervisee_version_id_mapping: dict[str, str] | None = None,
        contract_codes: list[str] | None = None,
        smart_contract_version_ids: list[str] | None = None,
        templates_parameters: list[dict[str, str]] | None = None,
        contract_config: ContractConfig | None = None,
        supervisor_contract_config: SupervisorConfig | None = None,
        account_creation_events: list[dict[str, Any]] | None = None,
        internal_account_ids: list[str] | dict[str, str] | None = None,
        flag_definition_ids: list[str] | None = None,
        output_account_ids: list[str] | None = None,
        output_timestamps: list[datetime] | None = None,
        debug: bool = False,
    ):
        internal_account_creation_events = []
        account_creation_events = account_creation_events or []
        default_events = []
        contract_codes = contract_codes or []
        smart_contract_version_ids = smart_contract_version_ids or []
        templates_parameters = templates_parameters or []
        flag_definition_ids = flag_definition_ids or []
        internal_account_ids = internal_account_ids or []
        contract_modules_to_simulate = []
        supervisee_version_id_mapping = supervisee_version_id_mapping or {}

        if internal_account_ids:
            for internal_account_id in internal_account_ids:
                # internal_account_ids is either a list of ids (in which case the accounts will be
                # instantiated as liability accounts or a dict with id:tside key-value pairs
                if isinstance(internal_account_ids, dict):
                    tside = internal_account_ids.get(internal_account_id, "LIABILITY")
                else:
                    tside = "LIABILITY"
                contract_file_path = (
                    EMPTY_ASSET_CONTRACT if tside == "ASSET" else EMPTY_LIABILITY_CONTRACT
                )
                internal_account = account_to_simulate(
                    timestamp=start_timestamp,
                    account_id=internal_account_id,
                    contract_file_path=contract_file_path,
                )
                internal_account_creation_events.append(internal_account)

        # putting internal account creation events at the front to ensure all events are in
        # chronological order, as mandated by the simulator endpoint
        account_creation_events = internal_account_creation_events + account_creation_events

        if flag_definition_ids:
            for flag_definition_id in flag_definition_ids:
                flag_definition_event = create_flag_definition_event(
                    timestamp=start_timestamp, flag_definition_id=flag_definition_id
                )
                default_events.append(flag_definition_event)

        for account in account_creation_events:
            contract_codes.append(account["contract_file_contents"])
            templates_parameters.append(account["template_parameters"])
            smart_contract_version_ids.append(account["smart_contract_version_id"])
            if account["event"]:
                default_events.append(account["event"])

        if supervisor_contract_code is not None:
            if not supervisee_version_id_mapping:
                raise ValueError(
                    "supervisee_version_id_mapping missing or empty for a test using "
                    "supervisor_contract_code"
                )

            supervisor_contract_code = replace_clu_dependencies(
                "UNKNOWN",
                supervisor_contract_code,
                supervisee_version_id_mapping,
                remove_clu_syntax_for_unknown_ids=True,
            )

        contract_codes = [
            replace_clu_dependencies("UNKNOWN", contract, remove_clu_syntax_for_unknown_ids=True)
            for contract in contract_codes
        ]

        contract_configs = (
            [contract_config]
            if contract_config
            else (
                supervisor_contract_config.supervisee_contracts
                if supervisor_contract_config
                else []
            )
        )

        (
            contract_module_linking_events,
            contract_modules_to_simulate,
        ) = _create_smart_contract_module_links(start_timestamp, contract_configs)
        default_events.extend(contract_module_linking_events)

        payload = self._api_post(
            "/v1/contracts:simulate",
            {
                "start_timestamp": _datetime_to_rfc_3339(start_timestamp),
                "end_timestamp": _datetime_to_rfc_3339(end_timestamp),
                "smart_contracts": _smart_contract_to_json(
                    contract_codes, templates_parameters, smart_contract_version_ids
                ),
                "supervisor_contracts": _supervisor_contract_to_json(
                    supervisor_contract_code, supervisor_contract_version_id
                ),
                "contract_modules": contract_modules_to_simulate,
                "instructions": [_event_to_json(event) for event in default_events + events],
                "outputs": create_derived_parameters_instructions(
                    output_account_ids, output_timestamps
                ),
            },
            timeout=timeout,
            debug=debug,
        )
        return payload


def _datetime_to_rfc_3339(dt):
    timezone_aware = dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None

    if not timezone_aware:
        raise ValueError("The datetime object passed in is not timezone-aware")

    return dt.astimezone().isoformat()


def _event_to_json(event):
    instruction = {
        "timestamp": _datetime_to_rfc_3339(event.time),
    }

    for key in event.event:
        instruction[key] = event.event[key]

    return instruction


def _smart_contract_to_json(
    contract_codes: list[str],
    templates_parameters: list[dict[str, str]],
    smart_contract_version_ids: list[str],
) -> list:
    return [
        {
            "code": code,
            "smart_contract_param_vals": template_parameter,
            "smart_contract_version_id": smart_contract_version_id
        }
        for code, template_parameter, smart_contract_version_id in zip(
            contract_codes, templates_parameters, smart_contract_version_ids
        )
    ]


def _supervisor_contract_to_json(supervisor_contract_code, supervisor_contract_version_id):
    """
    Helper that support the supervisor contract object. Although this is a list field,
    only one supervisor contract can currently be simulated for each request.
    :param supervisor_contract_code: Source code of the supervisor contract that is to be simulated.
    :param supervisor_contract_version_id: The ID that will be used as the supervisor contract
        version ID in the simulation and can be referenced by the simulation instructions.
    :return: a hypothetical list of supervisor contracts to simulate.
    """
    supervisor_contracts = []
    if supervisor_contract_code is not None:
        supervisor_contracts.append(
            {
                "code": supervisor_contract_code,
                "supervisor_contract_version_id": supervisor_contract_version_id,
            }
        )
    return supervisor_contracts


def _create_smart_contract_module_links(
    start: datetime, contract_configs: list[ContractConfig]
) -> tuple[list[SimulationEvent], list[dict[str, str]]]:
    events = []
    contract_modules_to_simulate = []
    existing_contract_modules = []
    for contract_config in contract_configs:
        alias_to_sc_version_id = {}
        if contract_config.linked_contract_modules:
            for contract_module in contract_config.linked_contract_modules:
                existing_module_version_id = get_existing_module_version_id(
                    contract_module, existing_contract_modules
                )
                if existing_module_version_id is not None:
                    contract_module_version_id = existing_module_version_id

                else:
                    contract_module_code = load_file_contents(contract_module.file_path)
                    contract_module_version_id = str(uuid.uuid4())
                    contract_module.version_id = contract_module_version_id

                    existing_contract_modules.append(contract_module)

                    details = {
                        "code": contract_module_code,
                        "contract_module_version_id": contract_module_version_id,
                    }
                    contract_modules_to_simulate.append(details)

                alias_to_sc_version_id[contract_module.alias] = contract_module_version_id

            aliases_as_str = "_".join(alias_to_sc_version_id.keys())
            events.append(
                create_smart_contract_module_versions_link(
                    timestamp=start,
                    link_id=f"sim_link_modules_{aliases_as_str}_with_contract_"
                    f"{contract_config.smart_contract_version_id}",
                    smart_contract_version_id=contract_config.smart_contract_version_id,
                    alias_to_contract_module_version_id=alias_to_sc_version_id,
                )
            )
    return events, contract_modules_to_simulate


def get_existing_module_version_id(
    contract_module: ContractModuleConfig,
    existing_contract_modules: list[ContractModuleConfig],
):
    for existing_module in existing_contract_modules:
        if contract_module.file_path == existing_module.file_path:
            return existing_module.version_id
