_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Inception Test Framework Configuration

## Approach

The test framework relies on configuration to define the environments that simulation and end-to-end (e2e) tests use. Our approach decouples code and configuration and aims to support multiple setups:

1. Configuration lives outside of the test framework code to avoid tightly coupling the two
2. We allow scalar configuration values to be passed in via the tests themselves, CLI arguments and OS environment variables
3. We allow more complex configuration values to be passed as file paths to json files, via CLI arguments and OS environment variables
4. The priority order is test > CLI Argument Value > OS Environment Variables

## Implementation

We currently expose the following settings.

| Name                    | Description                                                                | CLI Flag                  | Environment Variable        | Default                         | Comments                            |
|-------------------------|----------------------------------------------------------------------------|---------------------------|-----------------------------|---------------------------------|-------------------------------------|
| Environment Config Path | Path to the json file containing environment configuration details         | --environment_config_path | INC_ENVIRONMENT_CONFIG_PATH | /config/environment_config.json | See below for example configuration |
| Framework Config Path   | Path to the json file containing framework configuration details           | --framework_config_path   | INC_FRAMEWORK_CONFIG_PATH   | /config/framework_config.json   | See below for example configuration |
| Environment Name        | Name of the environment to use, as per contents of Environment Config file | --environment_name        | INC_ENVIRONMENT_NAME        | N/A                             | Overrides Framework Config          |

### Example Configuration

#### Environment Config

The value should point to a json file containing a dictionary of environment names to environment attributes. For example:

```json
{
  "my_environment": {
    "ops_dash_url": "https://ops.my.env.tmachine.io",
    "core_api_url": "https://core-api.my.env.io",
    "data_loader_api_url": "https://data-loader-api.my.env.io",
    "workflow_api_url": "https://workflows-api.my.env.io",
    "prometheus_api_url": "https://metrics.internal.tmachine.io",
    "kafka": {
      "bootstrap.servers": "kafka.kafka-v2.my.env.io"
    },
    "cluster": "my_k8s_cluster",
    "namespace": "my_k8s_namespace",
    "service_account_name": "",
    "service_account_id": "",
    "access_token": "<INSERT_TOKEN>"
  }
}
```

#### Framework Config

The value should point to a json file containing the default environments to use for e2e and sim framework tests. These names must be present in the environment config. For example:

```json
{
    "e2e": {"environment_name": "my_environment"},
    "sim": {"environment_name": "my_environment"}
}
```

#### Environment Name

Individual e2e test modules can explicitly specify the environment to run against in case it is not possible to overcome certain dependencies. For example, there may be only one environment where a specific component required for a test is currently deployed, so the test must use this environment. For example

```python
endtoend.testhandle.environment_name = "my_special_environment"
```

### Further Details

We use the `absl` distributed flag library (see <https://abseil.io/docs/python/>) to define the relevant CLI flags that each module needs. This allows to keep the definitions closer to where they are used. However, common sim/e2e flags are kept at `inception_sdk/common/config.py`.

We enable support for environment variables by setting the default FLAG values to an `os.getenv()` call:

```python
flags.DEFINE_string(
    ...
    default=os.getenv("INC_MY_ENV_VARIABLE", "my_default_value")
    ...
)
```

Each of our `TestCase` extensions must then ensure that flags are parsed, typically during `setUpClass`, and config values are extracted using `inception_sdk/common/config.py`'s `extract_environments_from_config()` function, and then passed into further setup as required. For example, this slightly simplified excerpt illustrates the required sequence of events.

```python
class End2Endtest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        flag_utils.parse_flags()
        endtoend.testhandle.use_kafka = FLAGS.use_kafka
        environment, available_environments = extract_environments_from_config()
```
