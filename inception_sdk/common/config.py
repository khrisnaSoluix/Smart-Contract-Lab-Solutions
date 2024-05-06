# standard libs
import logging
import os

# third party
from absl import flags

# inception sdk
from inception_sdk.vault.environment import Environment, load_environments

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
FLAGS = flags.FLAGS

# We add the INC_ prefix to avoid clashes with other tools' environment variables (e.g. ENVIRONMENT
# is very likely to be used elsewhere, whereas INC_ENVIRONMENT feels unique enough)
FLAG_PREFIX = "INC_"

# Each flag should attempt to get a default value from environment variables before using a
# hardcoded default. This allows users to either specify arguments via CLI or environment variables
# without much extra effort in the framework.
flags.DEFINE_string(
    name="environment_config_path",
    default=os.getenv(FLAG_PREFIX + "ENVIRONMENT_CONFIG_PATH", "config/environment_config.json"),
    help=f"Path to json file containing the config for each environment that the framework may"
    f" be used against. Can also be set via env variable {FLAG_PREFIX + 'ENVIRONMENT_CONFIG_PATH'}."
    f" Defaults to `current_working_directory/config/environment_config.json`",
)

flags.DEFINE_string(
    name="environment_name",
    default=os.getenv(FLAG_PREFIX + "ENVIRONMENT_NAME", ""),
    help=f"Environment to use, overriding the configuration present in the"
    f" json file specified by`--framework_config`. The `environment` value must be a key"
    f" present in the json file specified by `environment_config_path`. Can also be set via env"
    f" variable {FLAG_PREFIX + 'ENVIRONMENT_NAME'}. No default",
)


def extract_environments_from_config(
    environment_name: str = "", default_environment_name: str = ""
) -> tuple[Environment, dict[str, Environment]]:
    """

    :param environment_name: name of the environment to use to override config. Useful if a
    test should always be run against a given environment
    :param default_environment_name: name of the default environment to use if no other config
    is found
    :return: the environment to use and a dict of environment name to available environments
    """

    available_environments = {}

    # Env name taken from command call, CLI flags (which uses OS Env Vars for defaults) and finally
    # config
    if environment_name:
        log.info(f"Using environment {environment_name} - hardcoded (e.g. in test module)")
    elif FLAGS.environment_name:
        environment_name = FLAGS.environment_name
        log.info(f"Using environment {environment_name} - specified in CLI/OS Flags")
    elif default_environment_name:
        environment_name = default_environment_name
        log.info(
            f"Using environment {environment_name} - specified as default (e.g. framework config)"
        )

    if not environment_name:
        raise ValueError("No environment_name found in CLI flags, ENV variables")

    if FLAGS.environment_config_path:
        try:
            available_environments = load_environments(FLAGS.environment_config_path)
        except (IOError):
            log.warning(f"File at {FLAGS.environment_config_path} not found")

    if not available_environments or environment_name not in available_environments:
        raise ValueError(f"Environment {environment_name} not found in {available_environments}")

    return available_environments[environment_name], available_environments
