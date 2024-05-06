# Copyright @ 2020 Thought Machine Group Limited. All rights reserved.
# standard libs
import hashlib
import json
import logging
import os
import re
import uuid
from typing import Any, Union

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.common.python.file_utils import load_file_contents

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def create_contract_module(
    display_name: str,
    contract_module_id: str,
    request_id: str = "",
    description: str = "",
) -> dict[str, Any]:
    """
    Creates a new contract module by using the core api endpoint.
    :param request_id: str, unique string ID that is used to ensure the request is idempotent
    :param display_name: str, the human readable name of the contract module
    :param description: str, a description of the contract module contents
    :return: dict[str, object], the resulting contract module resource
    """
    if not request_id:
        request_id = uuid.uuid4().hex

    post_body = {
        "request_id": request_id,
        "contract_module": {
            "id": contract_module_id,
            "display_name": display_name,
            "description": description,
        },
    }

    post_body = json.dumps(post_body)

    resp = endtoend.helper.send_request("post", "/v1/contract-modules", data=post_body)
    log.info("Contract module %s created.", resp["id"])

    return resp


def create_contract_module_version(
    code: str,
    contract_module_id: str,
    display_name: str,
    request_id: str = "",
    description: str = "",
) -> dict[str, Any]:
    """
    Creates a contract module version resource by using the core api endpoint.
    :param request_id: str, unique string ID that is used to ensure the request is idempotent
    :param contract_module_id: str, the ID of the parent contract module resource
    :param code: str, the contract module code
    :param display_name: str, the human readable name of the contract module
    :param description: str, a description of the contract module version contents
    :return: dict[str, object], the resulting contract module version resource
    """
    if not request_id:
        request_id = uuid.uuid4().hex

    post_body = {
        "request_id": request_id,
        "contract_module_version": {
            "contract_module_id": contract_module_id,
            "display_name": display_name,
            "description": description,
            "code": code,
        },
    }

    post_body = json.dumps(post_body)

    resp = endtoend.helper.send_request("post", "/v1/contract-module-versions", data=post_body)
    log.info("Contract module %s version uploaded.", resp["id"])
    endtoend.testhandle.contract_module_version_name_to_id[display_name] = resp["id"]

    return resp


def upload_contract_modules(contract_modules: dict[str, dict[str, str]]) -> None:
    """
    Creates contract modules using the core api endpoint and then uploads the contract module
    version code. It then creates a link between the parent smart contract and the contract
    module version using the alias key defined in the smart contract.
    :param contract_modules: map of contract module ids and the corresponding dictionary of
    contract module properties e.g.:
    "math_module": {"path": "library/common/contract_modules/math_module.py",
                    "display_name": "math_module" - optional},
    :return:
    """
    if not contract_modules:
        return
    e2e_module_mapping = {}
    for contract_module_id, contract_module_properties in contract_modules.items():
        if "path" not in contract_module_properties:
            raise NameError(
                "Contract Module: {} not specified with path. "
                "Specified with {}".format(contract_module_id, str(contract_module_properties))
            )

        contract_module_file = contract_module_properties["path"]

        contract_module_data = load_file_contents(contract_module_file)

        display_name = contract_module_properties.get("display_name", contract_module_id)

        code_hash = hashlib.md5(
            (contract_module_data + display_name or "").encode("utf-8")
        ).hexdigest()
        e2e_unique_contract_module_id = "e2e_" + contract_module_id + "_" + code_hash

        contract_module = create_contract_module(
            request_id=e2e_unique_contract_module_id,
            display_name=display_name,
            contract_module_id=e2e_unique_contract_module_id,
        )

        contract_module_version = create_contract_module_version(
            request_id=contract_module["id"],
            contract_module_id=contract_module["id"],
            display_name=contract_module["display_name"],
            code=contract_module_data,
        )

        e2e_module_mapping[contract_module_id] = contract_module_version["id"]

    contract_module_aliases = get_contract_module_aliases(endtoend.testhandle.CONTRACTS)
    contract_to_version_id = {
        endtoend.testhandle.CONTRACTS[pid].get(
            "contract_id", pid
        ): endtoend.contracts_helper.get_current_product_version_id(pid)
        for pid in endtoend.testhandle.contract_pid_to_uploaded_pid
    }
    for contract in contract_module_aliases.keys():
        alias_to_contract_module_version_id = {}
        for alias in contract_module_aliases[contract]:
            alias_to_contract_module_version_id[alias] = e2e_module_mapping[alias]
        if alias_to_contract_module_version_id:
            link_contract_modules_to_contract(
                smart_contract_version_id=contract_to_version_id[contract],
                alias_to_contract_module_version_id=alias_to_contract_module_version_id,
            )


def link_contract_modules_to_contract(
    smart_contract_version_id: str,
    request_id: str = "",
    alias_to_contract_module_version_id: dict[str, str] = None,
) -> None:
    """
    Creates a smart contract module version link between a smart contract version and one or more
    contract module versions using the core api endpoint.
    """
    request_id = uuid.uuid4().hex

    post_body = {
        "request_id": request_id,
        "smart_contract_module_versions_link": {
            "smart_contract_version_id": smart_contract_version_id,
            "alias_to_contract_module_version_id": alias_to_contract_module_version_id,
        },
    }

    post_body = json.dumps(post_body)

    resp = endtoend.helper.send_request(
        "post", "/v1/smart-contract-module-versions-links", data=post_body
    )
    log.info(f"Contract module(s) linked, id {resp['id']}.")


def get_contract_module_aliases(
    contracts: dict[str, dict[str, Union[str, dict[str, str]]]]
) -> dict[str, list[str]]:
    """
    Uses a regex to parse the smart contract code and give back a list of the contract module
    aliases which are declared.
    """
    contract_module_aliases = {}
    for contract_id, contract_properties in contracts.items():
        if "path" in contract_properties:
            contract_data = load_file_contents(contract_properties["path"])

            # working example of the regex code is here https://regex101.com/r/Ch8G8V/1
            regex = r"(?P<alias_prefix>alias=[\'\"]?)(?P<alias>[\w\d]*)(?P<suffix>[\'\"]?)"  # noqa: E501
            contract_module_aliases[contract_id] = [
                match.group("alias") for match in re.finditer(regex, contract_data)
            ]

    return contract_module_aliases
