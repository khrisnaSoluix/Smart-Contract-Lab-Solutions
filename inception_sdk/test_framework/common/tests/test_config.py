# standard libs
import json
from unittest import TestCase, mock

# inception sdk
import inception_sdk.common.python.flag_utils as flag_utils

MOCK_ENV_VARS = {
    "INC_FRAMEWORK_CONFIG_PATH": "os_env_framework_config_path",
}

# os.environ is used at import time, so patching in test setup is too late
with mock.patch.dict("os.environ", MOCK_ENV_VARS) as mock_os_environ:
    # inception sdk
    import inception_sdk.test_framework.common.config as config


DEFAULT_FRAMEWORK_CONFIG_JSON = json.dumps(
    {"e2e": {"environment_name": "default_env"}, "sim": {"environment_name": "default_env"}}
)


@mock.patch.object(config, "extract_environments_from_config")
@mock.patch.object(config, "load_file_contents")
@mock.patch.object(config, "FLAGS")
class ConfigExtractionTest(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.maxDiff = None
        return super().setUpClass()

    def test_default_envs_read_from_framework_config(
        self, flags_mock, load_file_contents_mock, extract_environments_from_config: mock.Mock
    ):
        # Everything configured to return default_env except for the function parameter
        type(flags_mock).environment_name = mock.PropertyMock(return_value="default_env")
        load_file_contents_mock.return_value = DEFAULT_FRAMEWORK_CONFIG_JSON

        config.extract_framework_environments_from_config(
            environment_purpose=config.EnvironmentPurpose.E2E, environment_name="non_default_env"
        )

        extract_environments_from_config.assert_called_once_with(
            environment_name="non_default_env", default_environment_name="default_env"
        )

    @mock.patch.object(config, "log")
    def test_default_envs_not_set_if_framework_config_file_missing(
        self,
        log: mock.Mock,
        flags_mock,
        load_file_contents_mock,
        extract_environments_from_config: mock.Mock,
    ):
        # Everything configured to return default_env except for the function parameter
        type(flags_mock).environment_name = mock.PropertyMock(return_value="default_env")
        type(flags_mock).framework_config_path = mock.PropertyMock(return_value="some_path")
        load_file_contents_mock.side_effect = IOError()

        config.extract_framework_environments_from_config(
            environment_purpose=config.EnvironmentPurpose.E2E, environment_name="non_default_env"
        )

        log.warning.assert_called_once_with(
            "Could not load framework default config. File at some_path not found"
        )
        extract_environments_from_config.assert_called_once_with(
            environment_name="non_default_env", default_environment_name=""
        )


class CommonFlagSetupTest(TestCase):
    # These tests all rely on the import-level os.environ patch
    def test_framework_path_config_defaults_to_os_env(
        self,
    ):
        flag_utils.parse_flags(argv=[])
        self.assertEqual(config.FLAGS.framework_config_path, "os_env_framework_config_path")
