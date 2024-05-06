# standard libs
import json
import re
from collections import defaultdict
from glob import glob
from itertools import chain
from logging import basicConfig, getLogger
from os import environ, getcwd, path
from typing import Any
from unittest import TestCase, main

# third party
from yaml import safe_load

# inception sdk
import inception_sdk.common.python.file_utils as file_utils
import inception_sdk.tools.common.tools_utils as tools_utils
import inception_sdk.tools.deployment_utils.deployment_utils as deployment_utils

log = getLogger(__name__)
basicConfig(level=environ.get("LOGLEVEL", "INFO"))
flatten = chain.from_iterable

PRODUCTDIR = "library/"
LIBRARY_MANIFEST = "library/library_manifest.yaml"
SHARED_WORKFLOWS = ["simple_notification"]
RESOURCE_MAPPING = {
    "ACCOUNT SCHEDULE TAGS": "/account_schedule_tags/*.resource.yaml",
    "SMART CONTRACTS": "/contracts/*contract.resource.yaml",
    "WORKFLOW DEFINITIONS": "/workflows/*.resources.yaml",
    "FLAG DEFINITIONS": "/flag_definitions/*.resource.yaml",
    "CALENDARS": "/calendars/*.resource.yaml",
    "SUPERVISOR SMART CONTRACTS": "/contracts/*.resources.yaml",
    "SUPERVISOR SMART CONTRACT VERSIONS": "/contracts/*.resources.yaml",
    "SMART CONTRACT MODULE VERSIONS LINKS": "/contracts/*link.resource.yaml",
}

COMMON_RESOURCE_MAPPING = {
    "INTERNAL ACCOUNT SMART CONTRACTS": "common/internal_accounts/contracts/*.resources.yaml",
    "INTERNAL ACCOUNTS": "common/internal_accounts/*.resource.yaml",
    "CONTRACT MODULES": "common/contract_modules/*.resources.yaml",
    "CONTRACT MODULE VERSIONS": "common/contract_modules/*.resources.yaml",
}

SMART_CONTRACT_FILE_MAPPING = {
    "SMART CONTRACTS": "/contracts/*.py",
}

# Used to exclude rendered contracts that still have modules from manifest tests, as these tests
# rely on parsing the contract to scan for module usage and the rendered contracts in the repo
# are just placeholders. When all modules have been removed from products we will remove the tests
# altogether
PRODUCTS_EXCLUDED_FROM_MANIFEST_TESTS = ["us_products_v3"]


class ProductManifestTest(TestCase):
    """
    Tests that files, resources, and references in the product manifest are
    consistently named and present. Executes the CLU validate command.
    Currently supports tests for the following resources:
     - SMART CONTRACTS
     - WORKFLOW DEFINITIONS
     - INTERNAL ACCOUNTS
     - CONTRACT MODULES
    """

    def setUp(self) -> None:
        self.product_manifest_file_paths = glob(PRODUCTDIR + "*_manifest.yaml")
        if LIBRARY_MANIFEST in self.product_manifest_file_paths:
            self.product_manifest_file_paths.remove(LIBRARY_MANIFEST)
        self.parsed_product_manifests = tools_utils.parse_product_manifests(
            self.product_manifest_file_paths
        )
        self.parsed_resource_files = parse_resource_files(self.parsed_product_manifests)
        self.resources_by_type = get_all_resources(self.parsed_resource_files)
        self.maxDiff = None

    def test_workflow_definition_id_matches_filename_and_id(self):
        """
        Test that the workflow resource ID, workflow definition ID, and workflow filename are
        consistent.
        """
        discrepancies = []
        workflow_ids = {}

        for workflow_resource in self.resources_by_type["WORKFLOW_DEFINITION_VERSION"]:
            workflow_ids["workflow_resource_id"] = workflow_resource.get("id").lower()

            payload = safe_load(workflow_resource["payload"])
            workflow_resource_filename = extract_filename_from_clu_notation(
                payload["workflow_definition_version"]["specification"]
            )
            if workflow_resource_filename in SHARED_WORKFLOWS:
                continue

            workflow_ids["workflow_resource_filename"] = workflow_resource_filename

            workflow_ids["workflow_definition_id"] = payload["workflow_definition_version"][
                "workflow_definition_id"
            ].lower()

            unique_workflow_ids = set(workflow_ids.values())

            # Add any instances where the naming of the resource is inconsistent
            if len(unique_workflow_ids) > 1:
                discrepancies.append(
                    {
                        f"{list(workflow_ids.values())}",
                    }
                )

        if len(discrepancies) > 0:
            raise AssertionError(
                f"the following workflow naming discrepancies exist: {discrepancies}"
            )

    def test_crosscheck_workflow_resources_and_product_manifest(self):
        """
        Test that each wf present in the <product>.resources.yaml is referenced in the manifest
        and that each <wf resource> in the manifest is referenced in the <product>.resources.yaml
        """
        id_sources = {}
        manifest_ids = []

        id_sources["workflow_resource_ids"] = set(
            workflow_resource.get("id").lower()
            for workflow_resource in self.resources_by_type["WORKFLOW_DEFINITION_VERSION"]
        )

        manifest_ids = [
            self.parsed_product_manifests[manifest].get("WORKFLOW DEFINITIONS")
            for manifest in self.parsed_product_manifests
            if self.parsed_product_manifests[manifest].get("WORKFLOW DEFINITIONS") is not None
        ]

        id_sources["manifest_ids"] = {i.lower() for sublist in manifest_ids for i in sublist}

        resource_id_difference = id_sources["workflow_resource_ids"].difference(
            id_sources["manifest_ids"]
        )

        if len(resource_id_difference) > 0:
            raise AssertionError(
                f"resources exist in resource file but not in product manifest: "
                f"{resource_id_difference}"
            )

    def test_all_workflow_files_are_included_in_associated_resource_file(self):
        """
        Test that each wf present in the directory also exists in the <product>.resources.yaml
        e.g. my_wf.yaml exists in the directory but is not referenced in the resources.yaml
        """
        resource_workflow_file_tags = set()
        workflow_files = set(
            path.splitext(path.basename(file))[0]
            for file in glob(PRODUCTDIR + "*/workflows/*.yaml")
            if "resources.yaml" not in file
        )
        for workflow_resource in self.resources_by_type["WORKFLOW_DEFINITION_VERSION"]:
            payload = safe_load(workflow_resource["payload"])
            resource_workflow_file_tags.add(
                extract_filename_from_clu_notation(
                    payload["workflow_definition_version"]["specification"]
                )
            )

        resource_id_difference = workflow_files.difference(resource_workflow_file_tags)
        workflow_files_difference = resource_workflow_file_tags.difference(workflow_files)

        if len(resource_id_difference) > 0:
            raise AssertionError(
                "workflows exist in product folder with no supporting resource in resource file"
            )

        if len(workflow_files_difference) > 0:
            raise AssertionError(
                "resources exist in resource file with no supporting worfklow file"
            )

    def test_crosscheck_contract_filename_and_resource_ids(self):
        """
        Test that the contract resource ID, code ID, and product ID are consistent.
        """
        discrepancies = []

        # We support manifests that don't have any contract versions
        for contract_resource in self.resources_by_type.get("SMART_CONTRACT_VERSION", []):
            contract_ids = set()
            contract_ids.add(contract_resource["id"])
            payload = safe_load(contract_resource["payload"])
            contract_ids.add(payload["product_version"]["product_id"])

            # Add any instances where the naming of the resource is inconsistent
            if len(contract_ids) > 1:
                discrepancies.append(
                    {
                        "error": f"Contract IDs are inconsistent within the resource: "
                        f"{contract_ids}",
                    }
                )
        if len(discrepancies) > 0:
            raise AssertionError(f"{discrepancies}")

    def test_all_contract_files_are_included_in_associated_resource_file(self):
        """
        Test that each contract present in the directory also exists in the <product>.resource.yaml
        e.g. my_product.py exists in the directory but is not referenced in the resource.yaml
        Note: if the BUILD file does not contain a reference to the contract
        file then the test could pass despite this check.
        """
        resource_contract_ids = set()
        contract_files = set(path.basename(file) for file in glob(PRODUCTDIR + "*/contracts/*.py"))

        for contract_resource in self.resources_by_type.get(
            "SMART_CONTRACT_VERSION", []
        ) + self.resources_by_type.get("SUPERVISOR_CONTRACT_VERSION", []):
            payload = safe_load(contract_resource["payload"])
            if "product_version" in payload:
                resource_contract_ids.add(
                    extract_filename_from_clu_notation(
                        payload["product_version"]["code"], with_extension=True
                    )
                )
            if "supervisor_contract_version" in payload:
                resource_contract_ids.add(
                    extract_filename_from_clu_notation(
                        payload["supervisor_contract_version"]["code"],
                        with_extension=True,
                    )
                )

        resource_id_difference = contract_files.difference(resource_contract_ids)
        contract_files_difference = resource_contract_ids.difference(contract_files)

        if len(resource_id_difference) > 0:
            raise AssertionError(
                f"Contracts exist in product folder with no supporting resource in resource file: "
                f" {resource_id_difference}"
            )

        if len(contract_files_difference) > 0:
            raise AssertionError(
                f"resources exist in resource file with no supporting contract file: "
                f"{contract_files_difference}"
            )

    def test_crosscheck_contract_resources_and_product_manifest(self):
        """
        Test that the contract ID in the product manifest match those in the
        associated resource.yaml.
        """

        contract_resource_ids = set(
            contract_resource["id"]
            for contract_resource in self.resources_by_type["SMART_CONTRACT_VERSION"]
        )

        # some manifests contain multiple smart contracts and do not map 1-to-1 between
        # the <product>_manifest.yaml and the referenced smart contracts (e.g US Products)
        manifest_ids = set(
            flatten(
                # We support manifests that don't have any contract versions
                self.parsed_product_manifests[manifest].get("SMART CONTRACTS", [])
                for manifest in self.parsed_product_manifests
            )
        )

        resource_id_difference = contract_resource_ids.difference(manifest_ids)
        manifest_id_difference = manifest_ids.difference(contract_resource_ids)

        if len(resource_id_difference) > 0:
            raise AssertionError(
                f"resources exist in resource file but not in product manifest: "
                f" {resource_id_difference}"
            )

        if len(manifest_id_difference) > 0:
            raise AssertionError(
                f"resources exist in product manifest but not in resource file: "
                f" {manifest_id_difference}"
            )

    def test_internal_accounts_match_internal_account_contracts_in_product_manifest(
        self,
    ):
        """
        Test that all internal accounts mentioned in the manifest have a matching contract
        and vice versa.
        """
        discrepancies = []

        for manifest in self.parsed_product_manifests:
            internal_accounts = self.parsed_product_manifests[manifest].get("INTERNAL ACCOUNTS", [])
            internal_account_contracts = self.parsed_product_manifests[manifest].get(
                "INTERNAL ACCOUNT SMART CONTRACTS", []
            )

            internal_accounts = set(
                internal_account.lower()
                for internal_account in self.parsed_product_manifests[manifest].get(
                    "INTERNAL ACCOUNTS", []
                )
            )

            internal_account_contracts = set(
                contract[:-9] if contract.endswith("_contract") else contract
                for contract in internal_account_contracts
            )

            internal_accounts_differences = internal_accounts.symmetric_difference(
                internal_account_contracts
            )

            if internal_accounts_differences:
                discrepancies.append(
                    {
                        "manifest_file": manifest,
                        "error": f"Not all internal accounts have a matching named contract: "
                        f"{internal_accounts_differences}",
                    }
                )
        if len(discrepancies) > 0:
            raise AssertionError(f"internal accounts discrepancies exist: {discrepancies}")

    def test_contract_modules_and_links(self):
        """
        Test that contract modules mentioned in the manifest have a corresponding
        contract module version and smart contract module link.
        """
        discrepancies = []

        for manifest in self.parsed_product_manifests:
            contracts = self.parsed_product_manifests[manifest].get("SMART CONTRACTS", [])
            contract_modules = self.parsed_product_manifests[manifest].get("CONTRACT MODULES", [])

            contract_module_versions = set(
                self.parsed_product_manifests[manifest].get("CONTRACT MODULE VERSIONS", [])
            )
            expected_module_versions = {f"{cm}_version" for cm in contract_modules}
            module_version_differences = contract_module_versions.symmetric_difference(
                expected_module_versions,
            )
            if module_version_differences:
                discrepancies.append(
                    {
                        "manifest_file": manifest,
                        "error": f"Not all contract modules have a matching module version: "
                        f"{module_version_differences}",
                    }
                )

            contract_module_versions_links = self.parsed_product_manifests[manifest].get(
                "SMART CONTRACT MODULE VERSIONS LINKS", []
            )
            num_links = len(contract_module_versions_links)
            expected_links = len(contracts) if contract_modules else 0
            if num_links != expected_links:
                discrepancies.append(
                    {
                        "manifest_file": manifest,
                        "error": f"Expected {expected_links} contract module versions links, "
                        f"but got {num_links}",
                    }
                )

        if len(discrepancies) > 0:
            raise AssertionError(f"Contract module discrepancies exist: {discrepancies}")

    def test_manifests_and_smart_contracts_for_correct_contract_module_resource_references(self):
        """
        Test that contract modules included in the smart contract files have corresponding
        smart contract module link resources in the respective product manifest.
        Test that all contract module resources referenced on each product manifest exist in the
        (one or many) smart contract resources referenced in the respective product manifest.
        """
        discrepancies = []

        smart_contract_modules_refs = find_contract_modules_in_smart_contract_files(
            self.parsed_product_manifests
        )
        for product in self.parsed_product_manifests:
            if product in PRODUCTS_EXCLUDED_FROM_MANIFEST_TESTS:
                continue
            contracts = self.parsed_product_manifests[product].get("SMART CONTRACTS", [])
            contract_modules = self.parsed_product_manifests[product].get("CONTRACT MODULES", [])
            referenced_contract_modules = []
            for contract in contracts:
                if contract_modules and contract in smart_contract_modules_refs.keys():
                    referenced_contract_modules.extend(smart_contract_modules_refs[contract])

            unique_expected_contract_modules = set(contract_modules)
            unique_referenced_contract_modules = set(referenced_contract_modules)

            if unique_expected_contract_modules - unique_referenced_contract_modules:
                discrepancies.append(
                    {
                        "manifest_file": product,
                        "error": f"Expected {unique_expected_contract_modules} contract module "
                        f"references, "
                        f"but got {unique_referenced_contract_modules} in smart contract(s)",
                    }
                )
        if len(discrepancies) > 0:
            raise AssertionError(f"Contract module discrepancies exist: {discrepancies}")

    def test_clu_validate_returns_no_errors(self):
        """
        Test that executing the CLU command `validate` for each manifest produces no errors.
        """
        if not tools_utils.check_if_plz():
            # Are we executing in the right place and in the right state
            tools_utils.check_banking_layer_repo()
            home_dir = getcwd()
        else:
            home_dir = getcwd().split("plz-out")[0]
        clu_path = path.join(home_dir, tools_utils.get_clu_path_by_system())
        clu_validation_errors = []

        for product_manifest_file_path in self.product_manifest_file_paths:
            full_product_manifest_file_path = path.join(home_dir, product_manifest_file_path)

            _, clu_output_json = deployment_utils.run_clu(
                clu_path=clu_path,
                function="validate",
                manifest_path=full_product_manifest_file_path,
                output_format="json",
            )
            clu_output = json.loads(clu_output_json[0])

            if "validate" not in clu_output:
                raise AssertionError(
                    f"CLU validation failed for {product_manifest_file_path}: {clu_output}"
                )

            clu_validation_errors.extend(
                (product_manifest_file_path, resource_name, output["error"])
                for resource_name, output in clu_output["validate"].items()
                if not output["valid"]
            )

        if clu_validation_errors:
            raise AssertionError(f"CLU validation errors found: {clu_validation_errors}")


def parse_resource_files(
    parsed_product_manifests: dict[str, dict[str, list[str]]]
) -> dict[str, list[dict[str, Any]]]:
    """
    Takes a dict of product manifests and searches for the actual resource
    yaml files associated with the named resource in the manifest.
    The resource.yaml file is read and parsed to extract the contents.
    A dict containing all the associated resources per product is returned.

    :param parsed_product_manifests: dict of products and their resources
    :return: dict of product id to a list of dicts, each representing parsed resources.
    These parsed resource dicts are key-value pairs as per the underlying resources. They are
    typically str:str, but not always, depending on yaml's parsing (e.g. a true/false value will
    be parsed to a bool type)
    """
    parsed_resources = {}
    for product, resources in parsed_product_manifests.items():
        multiple_resources_file_contents = []
        single_resource_file_contents = []
        product_resource_ids = set()
        for resource_type, resource_ids in resources.items():
            product_resource_ids.update(resource_ids)
            resource_file_paths = []
            if RESOURCE_MAPPING.get(resource_type):
                resource_ext = RESOURCE_MAPPING.get(resource_type)
                if not resource_ext:
                    log.warning(
                        f"No mapping found for product `{product}` and "
                        f"resource type `{resource_type}`. Won't retrieve file paths"
                    )
                    break
                resource_file_paths.extend(glob(PRODUCTDIR + product + resource_ext))
            elif COMMON_RESOURCE_MAPPING.get(resource_type):
                resource_ext = COMMON_RESOURCE_MAPPING.get(resource_type)
                if not resource_ext:
                    log.warning(
                        f"No mapping found for product `{product}` and "
                        f"resource type `{resource_type}`. Won't retrieve file paths"
                    )
                    break
                resource_file_paths.extend(glob(PRODUCTDIR + resource_ext))
            else:
                log.warning(f"Unrecognised resource type `{resource_type}`")
                break
            for resource_file_path in resource_file_paths:
                with open(resource_file_path, "r", encoding="utf-8") as resource_file:
                    resource_file_contents = safe_load(resource_file)
                if resource_ext.endswith("resources.yaml"):
                    multiple_resources_file_contents.append(resource_file_contents.get("resources"))
                else:
                    single_resource_file_contents.append(resource_file_contents)
        flat_list = list(flatten(multiple_resources_file_contents))
        resources = flat_list + single_resource_file_contents
        parsed_resources[product] = [r for r in resources if r["id"] in product_resource_ids]

    return parsed_resources


def find_contract_modules_in_smart_contract_files(
    parsed_product_manifests: dict[str, dict[str, list[str]]]
) -> dict[str, list[str]]:
    """
    Takes a dict of product manifests and searches for the actual smart contract
    files associated with the named sc resource in the manifest.
    The smart contract files are read and parsed to extract the contents.
    Return:
    A dict containing all the associated sc files and any referenced contract modules within them

    :param parsed_product_manifests: dict of products and their resources
    :return: dict, smart_contract_modules_refs
    """
    smart_contract_modules_refs = {}
    for product, resources in parsed_product_manifests.items():
        for resource_type in resources.items():
            if resource_type and SMART_CONTRACT_FILE_MAPPING.get(resource_type[0]):
                smart_contract_ext = SMART_CONTRACT_FILE_MAPPING.get(resource_type[0])
                if not smart_contract_ext:
                    log.warning(
                        f"No mapping found for product `{product}` and "
                        f"resource type `{resource_type}`. Won't retrieve file paths"
                    )
                    break
                smart_contract_file_paths = glob(PRODUCTDIR + product + smart_contract_ext)

                smart_contract_names_and_file_paths = zip(
                    resource_type[1], smart_contract_file_paths
                )
                for smart_contract_tuple in smart_contract_names_and_file_paths:
                    smart_contract_modules_refs[
                        smart_contract_tuple[0]
                    ] = extract_contract_module_alias_from_smart_contract(
                        file_utils.load_file_contents(smart_contract_tuple[1])
                    )

    return smart_contract_modules_refs


def extract_filename_from_clu_notation(
    external_file_clu_notation: str, with_extension: bool = False
) -> str:
    # regex to retrieve file name between @{.ext}
    # https://regex101.com/r/wWKAQK/1
    pattern = (
        r"@{(?:.+\/)?([A-Za-z0-9_\.]+)}" if with_extension else r"@{(?:.+\/)?([A-Za-z0-9_]+)\..*}"
    )
    matches = re.search(pattern, external_file_clu_notation)
    if matches := re.search(pattern, external_file_clu_notation):
        return matches.group(1).lower()
    else:
        raise ValueError(
            f"Could not retrieve filename from CLU notation `{external_file_clu_notation}`"
        )


def extract_contract_module_alias_from_smart_contract(smart_contract_file: str) -> list[str]:
    # regex to retrieve all contract module aliases defined in Smart Contract files
    # https://regex101.com/r/1YZJ9t/2
    pattern = r"ContractModule\(\n\s+alias=\"([A-Za-z]+)\""
    return re.findall(pattern, smart_contract_file)


def get_all_resources(
    parsed_resource_files: dict[str, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    """
    Takes the dict of parsed_resource_files relating to the parsed
    resource.yaml and restructures them so that they grouped
    by resource_type (e.g. workflow) rather than by product.

    :param parsed_resource_files: dict of products and extracted
                                  resource.yaml data
    :return: dict of resource type to list of corresponding resources
    """
    resources_by_type = defaultdict(list)
    list_of_resources = (
        resource for product in parsed_resource_files.values() for resource in product
    )

    for resource in list_of_resources:
        resources_by_type[resource.get("type")].append(resource)
        if resource.get("resources") is not None:
            # unpack nested resources
            for nested_resource in resource.get("resources", []):
                resources_by_type[nested_resource.get("type")].append(nested_resource)

    return resources_by_type


if __name__ == "__main__":
    main(ProductManifestTest)
