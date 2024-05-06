# standard libs
import enum
import json
import logging
import os

# third party
from absl import flags

# inception sdk
from inception_sdk.common.config import FLAG_PREFIX, FLAGS, extract_environments_from_config
from inception_sdk.common.python.file_utils import load_file_contents
from inception_sdk.vault.environment import Environment

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class EnvironmentPurpose(enum.Enum):
    E2E = "e2e"
    SIM = "sim"


# Each flag should attempt to get a default value from environment variables before using a
# hardcoded default. This allows users to either specify arguments via CLI or environment variables
# without much extra effort in the framework.
flags.DEFINE_string(
    name="framework_config_path",
    default=os.getenv(FLAG_PREFIX + "FRAMEWORK_CONFIG_PATH", "config/framework_config.json"),
    help=f"Path to json file containing the default environment names to use for sim and e2e tests."
    f" Can also be set via env variable {FLAG_PREFIX + 'FRAMEWORK_CONFIG_PATH'}."
    f" Defaults to `current_working_directory/config/framework_config.json`",
)


def extract_framework_environments_from_config(
    environment_purpose: EnvironmentPurpose, environment_name: str = ""
) -> tuple[Environment, dict[str, Environment]]:
    """
    :param environment_purpose: what the environment will be used for: one of 'e2e' or 'sim'. This
    is used in conjunction with the framework_config to choose the right environment if no
    overrides are provided
    :param environment_name: name of the environment to use to override config. Useful if a
    test should always be run against a given environment
    :return: the environment to use and a dict of environment name to available environments
    """

    default_environment_name = ""

    # Env name taken from command call, CLI flags (which uses OS Env Vars for defaults) and finally
    # config
    if FLAGS.framework_config_path:
        try:
            framework_config = json.loads(load_file_contents(FLAGS.framework_config_path))
            default_environment_name = framework_config.get(environment_purpose.value, {}).get(
                "environment_name"
            )
        except (IOError):
            log.warning(
                f"Could not load framework default config. File at {FLAGS.framework_config_path}"
                " not found"
            )

    return extract_environments_from_config(
        environment_name=environment_name, default_environment_name=default_environment_name
    )
