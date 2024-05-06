# standard libs
import json
import logging
import os
from dataclasses import dataclass, field

# inception sdk
from inception_sdk.common.python.file_utils import load_file_contents

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@dataclass
class ServiceAccount:
    account_id: str = ""
    name: str = ""
    token: str = ""


@dataclass
class Environment:
    name: str
    core_api_url: str = ""
    ops_dash_url: str = ""
    data_loader_api_url: str = ""
    workflow_api_url: str = ""
    kafka_config: dict[str, bool | int | str] = field(default_factory=dict)
    service_account: ServiceAccount = field(default_factory=ServiceAccount)
    prometheus_api_url: str = ""
    cluster: str = ""
    namespace: str = ""


def load_environment(name: str, env_definition: dict) -> Environment:
    kafka_config = env_definition.pop("kafka", {})
    service_account_id = env_definition.pop("service_account_id")
    service_account_name = env_definition.pop("service_account_name")
    service_account_token = env_definition.pop("access_token")

    return Environment(
        name=name,
        kafka_config=kafka_config,
        service_account=ServiceAccount(
            account_id=service_account_id,
            name=service_account_name,
            token=service_account_token,
        ),
        **env_definition,
    )


def load_environments(file_path: str) -> dict[str, Environment]:
    """
    Load multiple environments from a JSON file. Expects the JSON file to be a dictionary of
    environment_name -> env_config
    :param file_path: path to the JSON file
    :return: environments, initialised from JSON file contents
    """

    environments = {
        env_name: load_environment(env_name, env_definition=env)
        for env_name, env in json.loads(load_file_contents(file_path)).items()
    }

    return environments
