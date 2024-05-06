<!-- markdownlint-disable MD033 -->
_© (Thought Machine Group Limited) (2021)_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Deploying Configuration Layer Content to Vault

## Purpose

This document describes:

- where to look for further information on deploying configuration layer content
- different deployment scenarios and how to choose the right tool for the scenario
- how to deploy configuration layer content onto a Vault instance
- how the Inception Deployment Utils extend the functionality of the Configuration Layer Utility
- how to resolve common issues encountered when deploying configuration layer content

## Prerequisites

**Deployment Utils**

- Python 3.9 installed with the packages specified in `requirements.txt`
- access to the Vault APIs

## Further Supporting Documentation

Users are advised to consult the following sources for further information and more detailed explanations. These resources are either supplied as part of the Inception Release Package or hosted on the Vault Documentation Hub:

1. `Configuration Layer Utility User Guide.pdf`
2. `https://docs.thoughtmachine.net/vault-core/latest/EN/reference/contracts/overview/#deployment_in_vault`

## 1. Deploying Configuration Layer Content

The Configuration Layer consists of Financial Products (e.g. a credit card) that are made up of Smart Contracts (in the form of `.py` files) and supporting Workflows (in the form of `.yaml` files). Each Financial Product may also have supporting resources such as Account Schedule Tags and Flag Definitions which must also be deployed to the Vault instance for the Product to work as intended. These resources can be defined in supporting `.resource(s).yaml` files.

Each Vault Release is shipped with the latest version of the Configuration Layer Utility (CLU). The CLU is a command line interface (CLI) tool for deploying and configuring the Configuration Layer resources in Vault. A Linux compatible binary (`clu-linux-amd64`) is shipped with Vault releases from 2.3.0+ and a Mac compatible binary (`clu-darwin-amd64`) since 2.8.0+. Refer to `Configuration Layer Utility User Guide.pdf` for more detailed information on how the tool works.

Each Inception Release contains an additional Deployment Utils Python tool which extends the functionality of the CLU as described further below. This is the recommended tool for managing Inception Configuration Layer content deployment.

### 1.1 Development and Testing

During the development and testing of Smart Contracts and Workflows, users may want to deploy work-in-progress versions of the files to their test environment. The testing framework included in the Inception Library (see `inception_sdk/test_framework`) provides tools for uploading Configuration Layer content by using the relevant API endpoints directly.

The test framework adopts a "shared nothing" approach so that each test has a unique set of resources. This enables multiple developers to work simultaneously on the same contract or workflow without disrupting the work of others and distinguish their test outputs. Briefly, the required resources are defined at the start of the test and helper functions append a unique ID to the resource and handle upload to the Vault instance.<sup id="a1">[1](#f1)</sup>

Once the changes to the configuration layer have been merged into the `master` version, then the Deployment Utils tool can be used to manage the deployment process onto a `staging` or `production` environment.

> **NOTE:** Resources which have been previously imported via other means (e.g. using the API directly or via a manual workflow) and then subsequently imported using the CLU tool may lead to idempotency issues that will be reported as failures by the CLU tool. Therefore the CLU tool should be used to manage all actual deployments of configuration layer content.

### 1.2 Supporting configuration content

Once the configuration layer content is ready for upload to Vault, supporting `.resource(s).yaml` files should be created (or updated) along with a top-level `manifest.yaml` which references the defined resources and defines the root of the CLU configuration pack. See the `library` folder for examples of the supporting configuration content.<sup id="a2">[2](#f2)</sup> A suggested directory structure is shown below.

```plaintext
product/
│   ├── account_schedule_tags
│   │   └── tag.resource.yaml
│   ├── contracts
│   │   ├── product.py
│   │   ├── product_contract.resource.yaml
│   │   └── product_contract_module_versions_link.resource.yaml
│   ├── flag_definitions
│   │   └── flag_definition.resource.yaml
│   └── workflows
│       ├── open_product.yaml
│       └── product_workflows.resources.yaml
└── product_manifest.yaml
```

### 1.3 Deploying to an Environment

Configuration layer content can be deployed using either the CLU directly or via the use of the Deployment Utils script (`inception_sdk/tools/deployment_utils/deployment_utils.py`). The Deployment Utils is recommended due to its additional functionality.

Steps:

1. Define each resource in a corresponding `.resource(s).yaml`
2. Reference these resources in a manifest, e.g. `manifest.yaml`
3. Validate the manifest using the Deployment Utils
4. Determine values for the command line arguments (e.g. manifest path, CLU path, config file path, and instance name)
5. Upload the manifest contents to Vault using the Deployment Utils

**What is the Deployment Utils script?**

The Deployment Utils script is an optional python wrapper tool that extends the import functionality of the CLU. Additional features that can be accessed through this tool include auto-activation of workflow versions after deployment, managed environment config and more.<sup id="a3">[3](#f3)</sup>

**Using the Deployment Utils**

The `deployment_utils.py` file is located under `inception_sdk/tools/deployment_utils` in the Inception Library.

- The `requirements.txt` included at the root level specifies the required third-party libraries that should be present in the user's Python environment.
- Users may need to update their PYTHONPATH environment variable to include the library dependencies in `inception_sdk/`.
- An environment config file in JSON format needs to be available in a reachable directory for the tool to be able to run. The Inception Library contains the file `environment_config.json` under `config/` which can be used as a reference.
- The tool must be run with the current working directory as the release directory (i.e. the directory containing library/, inception_sdk/ and tools/). The manifest must be provided as a relative path from the release directory.

> **NOTE**: If you are affected by idempotency issues (e.g. a resource was imported without CLU/Deployment Utils) you can increment the version number of relevant Smart Contracts and Workflows that reference Smart Contracts. However, as this will create new versions of these resources, it may lead to undesirable fragmentation in production. This can be mitigated by migrating accounts on older product versions in bulk via the /v1/account-migrations endpoint, or more granularly via the /v1/account-updates endpoint. <sup id="a4">[4](#f4)</sup>

***Validation***

```bash
python3.9 inception_sdk/tools/deployment_utils/deployment_utils.py --validate_manifest \
--manifest=library/<relevant_manifest>.yaml \
--clu=/path/to/clu_tool
```

***Import***

```bash
python3.9 inception_sdk/tools/deployment_utils/deployment_utils.py --import_manifest \
--manifest=library/<relevant_manifest>.yaml \
--clu=/path/to/clu_tool \
--environment_config=/path/to/environment_config.json \
--environment_name=$INSTANCE_NAME \
--activate_workflows
```

***Available Flags***

- `--manifest` - Path to the CLU manifest file to import or validate
- `--clu` - Path to the CLU binary
- `--log_level` - The log level to set the logger to
- `--environment_config` - Path to the json file storing the environment config
- `--environment_name` - Specify the environment name from the environment config to import the pack to.
- `--activate_workflows` - Set this flag if deployed workflow versions need to be activated (i.e. need to automatically be made the default versions).
- `--update_workflows_inst_config` - Set this flag if the instantiation configuration for the deployed workflows needs to be updated (by default, the instantiation configuration is empty after deployment on a clean environment). The setup files with the instantiation resources are at the product level in `[product]/workflows/tmp_[product]_inst_config.resources.yaml`. Keep in mind that any existing workflows instantiation configurations will be overwritten by the newly deployed configuration.
- `--auth_cookie` - User-specific authentication cookie used for ops-dash login. This flag is needed only if you also passed the `update_workflows_inst_config` flag.

An example command would be:

```bash
python3.9 inception_sdk/tools/deployment_utils/deployment_utils.py --import_manifest --manifest=[path_to_manifest_file] --clu=[path_to_clu_tool] --environment_config=[path_to_environment_config] --environment_name=[instance_name] --activate_workflows
```

In the screenshot below you can see how to retrieve the authentication cookie values from your browser DevTools, by logging into ops-dash in the environment where the workflows are/will be deployed and inspecting the headers of any graphql request. You will then need to copy the entire value of the cookie header, by right-clicking the header and selecting “Copy value”:

## Troubleshooting

### Validation Errors

```"failed to execute command: error validating resource pack: unable to validate resources: unable to load resources: resource not found for ID "```

A resource is listed in the `manifest.yaml` but has no corresponding resource in the associated `resource(s).yaml`. Either add the resource to the `resource(s).yaml` or remove the reference in the `manifest.yaml`.

### Deployment Errors

#### Missing Smart Contract Parameters

The `validate` command does not check that all parameters defined in the Smart Contract `.py` file are referenced in the associated `.resource.yaml` file. Thus, if a parameter is missing from the `.resource.yaml` it will only be detected when the CLU tries to deploy to Vault. In this case, add the parameter and re-run the command. Idempotency will guarantee that only resources which were unsuccessful in the previous run will be updated.

#### Resource with name and ID already exists

In the event that a resource (usually a Smart Contract or Workflow) with the same name and version number but different code already exists on your Vault instance, the CLU `deploy` will return an error such as:

```bash
SMART_CONTRACT_VERSION with ID us_savings_account was NOT IMPORTED successfully using a create action. Error message: received error response code 400: Product template with same version number 1.4.0 already exists. New contract template id: 0. Existing contract template id: 34810
```

for that resource and an exit code of `PARTIAL SUCCESS`. Often this is the result of users deploying via non-CLU methods. This is usually fixed by updating the version number of the underlying resource and re-running the CLU `deploy` step. Alternatively, users can consult the `Configuration Layer Utility User Guide.pdf` for more guidance on handling `Resource clashes during the import`.

#### Products with mixed migration strategies

The CLU allows the user to set the `migration_strategy` for products at the deployment stage. For example, there is an existing product called `Credit Card` on Vault which is backed by the `credit_card.py` smart contract and numerous accounts created from it. A new version is ready for upload but will only be used for new accounts. In addition, a new product called `Wallet` using `wallet.py`, which does not exist on the target Vault instance, is also included in the `manifest.yaml`. If the CLU tries to deploy using:

`"--migration_strategy=PRODUCT_VERSION_MIGRATION_STRATEGY_ADD_VERSION_APPLY_NEW_USERS"`

The deployment will automatically retry the `Wallet` with `"--migration_strategy=PRODUCT_VERSION_MIGRATION_STRATEGY_NEW_PRODUCT`. By default, all products in the Inception Library have their migration strategy set to `PRODUCT_VERSION_MIGRATION_STRATEGY_ADD_VERSION_APPLY_NEW_USERS` in the corresponding resource YAML as a convenience in order to benefit from the automatic retry functionality.

#### Changes to internal account products

The CLU requires a different migration strategy for internal account upgrades than for smart contracts:

`"--migration_strategy=PRODUCT_VERSION_MIGRATION_STRATEGY_ADD_VERSION_UPGRADE_INTERNAL_ACCOUNTS"`

The deployment util currently does not support it and will error for the internal accounts already exist in the environment. These are false alarms due to the fact that internal account products are dummy contracts that do not contain any actual logic, so as long as one version already exists, the library products will work.

---
<b id="f1">1.</b> See Appendix B of `Configuration Layer Utility User Guide.pdf` for further examples and details. [↩](#a1)

<b id="f2">2.</b> Further information on how to use and adapt the testing framework is included in `documentation/test_framework.md` [↩](#a2)

<b id="f3">3.</b> Future versions of the CLU will incorporate much of the Deployment Utils functionality but until then it is recommended to use the Deployment Utils wrapper to interact with the CLU. [↩](#a3)

<b id="f4">4.</b> This version increment is ensured between Inception releases, but if users make subsequent changes that they wish to deploy, it may need repeating. For example, if the `credit_card.py` smart contract was being imported for a second time and there were no changes to the code, then the version at the top of that file (e.g. `1.8.1`) would need to be incremented to `1.8.2`. [↩](#a4)
