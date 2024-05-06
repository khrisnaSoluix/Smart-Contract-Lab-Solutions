# standard libs
import json
import logging
import os
import platform
import subprocess
import tempfile
import uuid
from pathlib import Path
from shutil import copytree
from typing import IO, Any

# third party
import requests
import yaml

# inception sdk
from inception_sdk.common.config import extract_environments_from_config
from inception_sdk.common.python.flag_utils import FLAGS, flags, parse_flags
from inception_sdk.vault.environment import Environment

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("deployment_utils")

CLU_ERROR_KEYWORDS = ["FAIL", "failed to", "INVALID"]
CLU_WARNING_KEYWORDS = ["PARTIAL SUCCESS"]
EXPECTED_XSRF_TOKEN_LEN = 54

# mapping each type of instantiation config variable to the corresponding Vault object type and keys
# the variable names are to be used in the instantiation_resources list located in the tmp_resources
# yaml files for each product
WF_INST_CONFIG_MAPPING = {
    "Customers list": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_CUSTOMER",
        "contextKeys": [],
    },
    "Customer": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_CUSTOMER",
        "contextKeys": ["VAULT_OBJECT_TYPE_CUSTOMER"],
    },
    "Customer accounts list": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_ACCOUNT",
        "contextKeys": [],
    },
    "Customer account": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_ACCOUNT",
        "contextKeys": ["VAULT_OBJECT_TYPE_ACCOUNT"],
    },
    "Transactions list": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_TRANSACTION",
        "contextKeys": [],
    },
    "Transaction": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_TRANSACTION",
        "contextKeys": ["VAULT_OBJECT_TYPE_TRANSACTION"],
    },
    "Restriction sets list": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_RESTRICTION_SET",
        "contextKeys": [],
    },
    "Restriction set instance": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_RESTRICTION_SET",
        "contextKeys": ["VAULT_OBJECT_TYPE_RESTRICTION_SET"],
    },
    "Flags list": {"vaultObjectType": "VAULT_OBJECT_TYPE_FLAG", "contextKeys": []},
    "Flag instance": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_FLAG",
        "contextKeys": ["VAULT_OBJECT_TYPE_FLAG"],
    },
    "Products list": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_PRODUCT",
        "contextKeys": [],
    },
    "Product": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_PRODUCT",
        "contextKeys": ["VAULT_OBJECT_TYPE_PRODUCT"],
    },
    "Product version": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_PRODUCT_VERSION",
        "contextKeys": ["VAULT_OBJECT_TYPE_PRODUCT_VERSION"],
    },
    "Processes list": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_WORKFLOW_INSTANCE",
        "contextKeys": [],
    },
    "Payments list": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_PAYMENT",
        "contextKeys": [],
    },
    "Payment": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_PAYMENT",
        "contextKeys": ["VAULT_OBJECT_TYPE_PAYMENT"],
    },
    "Internal accounts list": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_INTERNAL_ACCOUNT",
        "contextKeys": [],
    },
    "Internal account": {
        "vaultObjectType": "VAULT_OBJECT_TYPE_INTERNAL_ACCOUNT",
        "contextKeys": ["VAULT_OBJECT_TYPE_INTERNAL_ACCOUNT"],
    },
    "Roles list": {"vaultObjectType": "VAULT_OBJECT_TYPE_ROLE", "contextKeys": []},
}

# the GraphQL mutation string used for updating the instantiation config in ops-dash
WF_INST_MUTATION_STRING = """
    mutation UpdateWorkflowInstantiationLinkMutation(
        $workflowDefinitionId: String!,
        $workflowInstantiationPrerequisites: [WorkflowInstantiationPrerequisiteInput!]!
    ) {
    updateWorkflowToPrerequisiteLink(
        workflowDefinitionId: $workflowDefinitionId,
        workflowInstantiationPrerequisites: $workflowInstantiationPrerequisites
        ) {
            workflowToPrerequisiteLink {
                workflowDefinitionId
                lastEditTimestamp
                workflowInstantiationPrerequisites {
                    vaultObjectType
                    contextKeys
                    __typename
                }
                __typename
            }
            __typename
        }
    }
"""


# multi-flag validators
def auth_cookie_must_be_set_to_update_workflow_inst_config(input_dict: dict[str, Any]) -> bool:
    if input_dict is None:
        return True

    return not (
        input_dict.get("update_workflows_inst_config") and input_dict.get("auth_cookie") == ""
    )


def import_manifest_must_be_set_to_provide_extra_flags(input_dict: dict[str, Any]) -> bool:
    if input_dict is None:
        return True

    return input_dict.get("import_manifest") or all(
        input_dict.get(flag) in {None, False, ""}
        for flag in ["auth_cookie", "activate_workflows", "update_workflows_inst_config"]
    )


# Flags
flags.DEFINE_bool(
    name="import_manifest",
    default=False,
    help="Set to import the specified manifest using CLU. Mutually exclusive with "
    "`validate_manifest`",
)
flags.DEFINE_bool(
    name="validate_manifest",
    default=False,
    help="Set to validate the specified manifest using CLU. Mutually exclusive with "
    "`import_manifest`",
)
flags.DEFINE_string(
    name="manifest",
    default="library/library_manifest.yaml",
    help="Path to the CLU manifest file to import or validate. This must be a relative path "
    "from the Inception repo/release folder you are running this tool from",
)
flags.DEFINE_string(name="clu", default="tools/clu-linux-amd64", help="Path to the CLU binary")
flags.DEFINE_bool(
    name="activate_workflows",
    default=False,
    help="Set this flag if deployed workflow versions need to be activated. Can only be passed "
    "if `import_manifest` is also set",
)
flags.DEFINE_bool(
    name="update_workflows_inst_config",
    default=False,
    help="Pass this flag if the instantiation config for deployed workflows needs to be updated. "
    "Can only be passed if `import_manifest` is also set",
)
flags.DEFINE_string(
    name="auth_cookie",
    default="",
    help="Authentication cookie used for ops-dash login"
    "Pass this argument only if you have also passed the update_workflows_inst_config flag"
    "Cookie can be retrieved from your browser DevTools, in the Network tab, by looking at"
    "the Headers of a graphql request and copying the value of the cookie header. "
    "Can only be passed if `import_manifest` is also set",
)

# Validation
flags.mark_bool_flags_as_mutual_exclusive(
    flag_names=["import_manifest", "validate_manifest"], required=True
)
flags.register_multi_flags_validator(
    flag_names=[
        "import_manifest",
        "auth_cookie",
        "update_workflows_inst_config",
        "activate_workflows",
    ],
    multi_flags_checker=import_manifest_must_be_set_to_provide_extra_flags,
    message="`import_manifest` must be set if providing one or more of `auth_cookie`, "
    "`update_workflows_inst_config` and `activate_workflows`",
)
flags.register_multi_flags_validator(
    flag_names=["auth_cookie", "update_workflows_inst_config"],
    multi_flags_checker=auth_cookie_must_be_set_to_update_workflow_inst_config,
    message="`auth_cookie` must be provided if `update_workflows_inst_config` is set",
)


def init_logger(log_level: str):
    """
    :param log_level: logging level name.
    :return:
    """
    logger.setLevel(log_level)


def check_cwd_is_inception_root() -> None:
    """
    Check the working directory is an inception repo or release folder. Plz defaults to running in
    the repo root, but if running via python binary directly any directory could be used
    """

    markers = ["library/", "inception_sdk/"]
    for testpath in markers:
        if not os.path.exists(os.path.join(os.getcwd(), testpath)):
            raise Exception(
                "The current working directory does not look like an Inception repo/release folder"
                ". This is determined by the presence of library/ and "
                "inception_sdk/ directories"
            )


def get_manifest_path(argument_path: str) -> tuple[str, str]:
    """
    Check the manifest path provided in args is relative and exists within the working directory
    Breaks down the path into path to the directory and actual file name
    """
    if os.path.isabs(argument_path):
        raise Exception(
            f"The manifest path {argument_path} provided in the arguments is not relative."
        )

    elif not (os.path.exists(argument_path)):
        raise Exception(
            f"The relative path {argument_path} does not exist in the repo/release folder root"
            f" {os.getcwd()}"
        )

    return os.path.dirname(argument_path), os.path.basename(argument_path)


def check_system() -> None:
    """
    Determine correct CLU path to use based on architecture
    :param clu_path: path to the standard clu binary
    :param clu_darwin_path: path to the darwin clu binary
    """

    current_system = platform.system()
    if current_system == "Linux":
        return
    elif current_system == "Darwin":
        return
    else:
        raise Exception(f"Unsupported system {current_system}")


def copy_resources(temp_dir, resource_root_dir="library") -> str:
    """
    Make a copy of the contents from resource root (where manifest is)
    and all its subdirs into a temporary directory
    :param temp_dir: the temporary directory
    :param resource_root_dir: root dir where deployment resources are
    :returns: the destination tmp dir
    """
    src = os.path.join(os.getcwd(), resource_root_dir)
    dst = os.path.join(temp_dir, resource_root_dir)
    copytree(src, dst)
    return dst


def run_deployment_utils(unknown_args: list[str]):
    check_system()
    # Ensuring we have in inception root directory and that we have a relative path makes things
    # much easier when creating temp directories for file manipulation
    check_cwd_is_inception_root()
    resource_root, file_name = get_manifest_path(FLAGS.manifest)

    if FLAGS.validate_manifest:
        logger.info(f"Validating manifest at {FLAGS.manifest}")
        run_clu(
            clu_path=FLAGS.clu,
            function="validate",
            manifest_path=FLAGS.manifest,
            additional_args=unknown_args,
        )
    elif FLAGS.import_manifest:
        # At this point we have validated that we're in an inception repo, so it's safe to create
        # a temp directory without risking copying huge amounts of data
        # TODO: do we still need this temp directory? It was initially required to modify temp
        # copies of files during import, but this is no longer required with newer CLU features
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as temp_dir:
            dst = copy_resources(temp_dir, resource_root)
            manifest_path = os.path.join(dst, file_name)

            logger.info(f"Importing manifest at {manifest_path} to {FLAGS.environment_name}")
            environment, _ = extract_environments_from_config()

            success, clu_output = run_clu(
                clu_path=FLAGS.clu,
                function="import",
                manifest_path=manifest_path,
                environment=environment,
                additional_args=unknown_args,
            )
            if success:
                post_processing(
                    clu_output=clu_output,
                    environment=environment,
                    activate_workflows=FLAGS.activate_workflows,
                    update_workflows_inst_config=FLAGS.update_workflows_inst_config,
                    auth_cookie=FLAGS.auth_cookie,
                    resource_root=resource_root,
                )
            else:
                logger.warning("Post Processing skipped due to error excuting CLU command")
    logger.info("Exiting Deployment Utils")


def run_clu(
    clu_path: str,
    function: str,
    manifest_path: str,
    environment: Environment | None = None,
    additional_args: list[str] | None = None,
    output_format: str = "text",
) -> tuple[bool, list[str]]:
    """
    Run the CLU command as per command-line args
    :param clu_path: path to the CLU binary
    :param function: name of the CLU function to run (import or validate)
    :param manifest_path: path to the CLU manifest file to deploy
    :param config: config for the relevant environment
    :param additional_args: additional arguments to be passed to CLU. Use at your own risk as it
     may disrupt logic (e.g. we parse standard output, so using json will break features)
    :param output_format: 'text' or 'json', as per CLU `output` flag
    :returns: tuple of
    - bool indicating success (true) or failure (false). Always True when using `json` output_format
    - list of str representing stdout from CLU. Will contain a single string if using
    `json` output_format
    """

    def _read_lines_from_io(io: IO | None = None) -> list[str]:
        output = []
        if io:
            # This way we output lines one-by-one as we get them from stdout, which provides
            # faster feedback to human users
            line = next(io, "")
            if line:
                _log_clu_output(line.strip())
                output.append(line)
        return output

    command = [clu_path, function, manifest_path, f"--output={output_format}"]
    if function != "validate":
        if environment is None:
            raise Exception("Environment config must be provided if function is not validate")
        command.append(f"--auth-token={environment.service_account.token}")
        command.append(f"--core-api={environment.core_api_url}")
        command.append(f"--workflows-api={environment.workflow_api_url}")

    if additional_args:
        command.extend(additional_args)

    # Using Popen instead of run to be able to both print and capture stdout
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if output_format == "json":
        return True, _read_lines_from_io(process.stdout)

    clu_output = []
    # Print output as we get it until the process is complete
    # Append each line to list as reading it from process.stdout pops the information
    while True:
        # Capture any output before the process has completed
        clu_output.extend(_read_lines_from_io(process.stdout))
        return_code = process.poll()
        if return_code is not None:
            success = return_code == 0
            if success:
                logger.info("Completed CLU command")
            else:
                logger.error("Error while executing CLU command")
            # At this point the process has completed, but we may have missed some output
            clu_output.extend(_read_lines_from_io(process.stdout))
            clu_output.extend(_read_lines_from_io(process.stderr))
            break
    return success, clu_output


def post_processing(
    clu_output: list[str],
    environment: Environment,
    activate_workflows: bool = False,
    update_workflows_inst_config: bool = False,
    auth_cookie: str = "",
    resource_root: str = "library",
) -> None:
    """
    :param clu_output: output from CLU deployment
    :param config: config for the relevant environment
    :param activate_workflows: drives whether deployed wf versions need to be set to default
    :param update_workflows_inst_config: decides whether the instantiation configuration
     needs to be updated for the deployed workflow versions
    :param xsrf_token: cross-site request forgery token used for making graphQL requests
    :param auth_cookie: authentication cookie containing three different tokens, used for
    ops-dash login
    :resource_root: root dir that contains manifest.yaml and all deployment resources
    """
    logger.info("Starting post processing")
    if activate_workflows:
        handle_workflow_activation(environment, clu_output)
    if update_workflows_inst_config:
        xsrf_token = extract_xsrf_token_from_cookie(auth_cookie)
        handle_workflows_inst_config(
            xsrf_token, auth_cookie, environment.ops_dash_url, resource_root
        )
    logger.info("Completed post processing")


def _log_clu_output(output: str):
    if any(keyword in output for keyword in CLU_ERROR_KEYWORDS):
        logger.error(output)
    elif any(keyword in output for keyword in CLU_WARNING_KEYWORDS):
        logger.warning(output)
    else:
        logger.info(output)


def handle_workflow_activation(environment: Environment, clu_output: list[str]):
    """
    Handles activating workflow definition versions after a CLU deployment
    :param environment: environment to use for workflow activation
    :param clu_output: list(str), the full output of a CLU deployment run
    """
    logger.info("Activating Workflow Versions")
    if clu_output == []:
        logger.error("CLU deployment output is empty! Workflow activation not possible.")
        return
    wf_activation_session = requests.sessions.Session()
    wf_activation_session.headers.update(
        {
            "X-Auth-Token": environment.service_account.token,
            "Content-Type": "application/json",
        }
    )

    for line in clu_output:
        line_stripped = line.strip()
        if deployment_status_successful(line_stripped):
            extracted_workflow_version_id = extract_workflow_version_id(line_stripped)
            logger.info(
                f'Setting version {extracted_workflow_version_id.get("version")} '
                f'of workflow {extracted_workflow_version_id.get("id")} as default.'
            )

            update_workflow_definition_version(
                wf_activation_session,
                workflow_api_url=environment.workflow_api_url,
                workflow_id=extracted_workflow_version_id["id"],
                workflow_ver=extracted_workflow_version_id["version"],
            )


def handle_workflows_inst_config(
    xsrf_token: str, auth_cookie: str, ops_dash_url: str, resource_root="library"
):
    """
    Updates the workflows instantiation configurations after a CLU deployment, based on the setup
    file for each product, found in [product]/workflows/tmp_[product]_inst_config.resources.yaml
    :param clu_output: the full output of a CLU deployment run
    :param xsrf_token: cross-site request forgery token used for making graphQL requests
    :param auth_cookie: authentication cookie containing three different tokens, used for
    ops-dash login
    :param ops_dash_url: url of the ops-dash for the specific environment where the workflows
    instantiation config needs to be updated
    :param resource_root: root dir where deployment resources reside
    """
    logger.info("Updating Workflow Instantiation Config")
    if not xsrf_token:
        logger.error("No xsrf token provided. Exiting")
        return None
    if not auth_cookie:
        logger.error("No authentication cookie provided. Exiting")
        return None

    # recursively find subdirs that contain /workflows/*tmp_resources.yaml
    file_glob = Path(os.path.join(os.getcwd(), resource_root)).rglob(
        "workflows/*tmp_resources.yaml"
    )
    graphQL_url = f"{ops_dash_url}/graphql"
    instantiation_errors = 0
    for file_path in file_glob:
        with open(file=file_path, mode="r", encoding="utf-8") as yaml_file:
            yaml_str = yaml_file.read()
            resources = yaml.safe_load(yaml_str)["resources"]
            for resource in resources:
                wf_def_id = resource["id"]
                logger.info(f"Updating inst config for workflow {wf_def_id}")
                wf_inst_resources = resource["instantiation_resources"]
                if not wf_inst_resources:
                    logger.warning(
                        "Workflow instantiation resources are not defined. Skipping workflow"
                    )
                    continue
                try:
                    update_workflow_instantiation_config(
                        wf_def_id,
                        wf_inst_resources,
                        graphQL_url,
                        xsrf_token,
                        auth_cookie,
                    )
                except Exception as e:
                    logger.exception(
                        f"Failed to update workflow instantiation config for definition {wf_def_id}"
                        f": {e}"
                    )
                    instantiation_errors += 1
    # these errors can get easily lost if there are many workflows, so provide a summary at the end
    if instantiation_errors:
        logger.error(
            f"{instantiation_errors} error(s) occured while setting workflowinstantiation config. "
            f"Check logs for further details"
        )


def extract_workflow_version_id(clu_output_line: str) -> dict[str, str]:
    """
    Parse a clu output line and extract the workflow version and id
    """
    workflow_version_id = clu_output_line.split("ID in Vault: ")[-1].replace('"', "").split(",")
    workflow_version = workflow_version_id[0]
    workflow_id = workflow_version_id[1]

    return {"version": workflow_version, "id": workflow_id}


def deployment_status_successful(
    clu_output_line: str, resource_type: str = "WORKFLOW_DEFINITION_VERSION"
) -> bool:
    """
    Checks if CLU line contains a workflow deployment and it's been successful.
    """
    # Filter out validation lines and other resource_types
    if resource_type in clu_output_line and "VALID" not in clu_output_line:
        if "successfully" in clu_output_line and "NOT IMPORTED" not in clu_output_line:
            return True
        logger.info(
            "The following has failed to deploy. Activation skipped.\n" f"{clu_output_line}"
        )
    return False


def update_workflow_definition_version(
    workflow_activation_session: requests.Session,
    workflow_api_url: str,
    workflow_id: str,
    workflow_ver: str,
):
    """
    Updates workflow definition version to default.
    :param wf_activation_session: a session to use for each activation call
    :param environment: environment to use for each activation call
    :param workflow_id: the workflow definition id of the version that needs updating.
    :param workflow_ver: version of the workflow to make default. Sample format -  "1.0.0".
    """
    body = {
        "request_id": uuid.uuid4().hex,
        "workflow_definition": {
            "default_workflow_definition_version_id": f"{workflow_ver},{workflow_id}"
        },
        "update_mask": {"paths": ["default_workflow_definition_version_id"]},
    }
    return workflow_activation_session.request(
        method="put",
        url=f"{workflow_api_url}/v1/workflow-definitions/{workflow_id}",
        data=json.dumps(body),
    )


def update_workflow_instantiation_config(
    wf_def_id: str,
    wf_inst_resources: list[str],
    graphQL_url: str,
    xsrf_token: str,
    auth_cookie: str,
):
    """
    Updates the instantiation configuration for a workflow.
    :param wf_def_id: the workflow definition id of the version that needs updating.
    :param wf_inst_resources: the names of the resources where the workflow can be
    instantiated from.
    :param graphQL_url: ops-dash url which will receive the mutation request
    :param xsrf_token: cross-site request forgery token used for making graphQL requests
    :param auth_cookie: authentication cookie containing three different tokens, used for
    ops-dash login
    :param errors: collection of errros that will be displayed at the end of running
    through the resources files.
    """
    current_inst_list = []
    for inst_resource in wf_inst_resources:
        if inst_resource in WF_INST_CONFIG_MAPPING:
            request_variables = WF_INST_CONFIG_MAPPING[inst_resource]
            current_inst_list.append(request_variables)
        else:
            raise Exception(
                f"Instantiation resource {inst_resource} for workflow {wf_def_id} does not exist "
                "in the configuration mapping"
            )
    if not current_inst_list:
        return None
    variables = {
        "workflowDefinitionId": wf_def_id,
        "workflowInstantiationPrerequisites": current_inst_list,
    }
    data = {"query": WF_INST_MUTATION_STRING, "variables": variables}
    json_data = json.dumps(data)
    header = {
        "x-xsrftoken": xsrf_token,
        "cookie": auth_cookie,
        "Content-type": "application/json",
    }
    try:
        resp = requests.post(url=graphQL_url, headers=header, data=json_data)
        resp.raise_for_status()
        json_resp = resp.json()
        # graphQL response may not be 4xx or 5xx yet still have errors inside
        if "errors" in json_resp.keys():
            raise Exception(f'Error in GraphQL response: {json_resp["errors"]}')
        else:
            logger.info(f"Updated successfully inst config for {wf_def_id}")
    except Exception as e:
        raise e


def extract_xsrf_token_from_cookie(auth_cookie: str) -> str:
    """
    Extracts the xsrf token from the auth_cookie.
    Splits the Auth cookie first on "_xsrf=" and the ";"
    Checks we have a _xsrf= marker before splitting
    Checks that we have a 54 character string before returning
    :param auth_cookie: auth cookie string to extract the xsrf token from
    """

    if "_xsrf" not in auth_cookie:
        raise ValueError(
            "_xsrf= not found in supplied auth cookie, please check --auth_cookie argument"
        )

    xsrf_token = auth_cookie.split("_xsrf=")

    xsrf_token = xsrf_token[1].split(";")

    if len(xsrf_token[0]) != EXPECTED_XSRF_TOKEN_LEN:
        raise ValueError("xsrf_token not expected length, please check --auth_cookie argument")

    return xsrf_token[0]


if __name__ == "__main__":
    unknown_args = parse_flags()
    init_logger(log_level=FLAGS.log_level)
    run_deployment_utils(unknown_args)
