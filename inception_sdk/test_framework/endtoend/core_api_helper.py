# Copyright @ 2020-2022 Thought Machine Group Limited. All rights reserved.
# standard libs
import json
import logging
import os
import random
import time
import uuid
from datetime import datetime, timezone
from dateutil import parser as dateparser
from enum import Enum
from typing import Any

# third party
from requests import HTTPError
from semantic_version import Version

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.test_framework.endtoend.helper import retry_decorator

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class AccountStatus(Enum):
    ACCOUNT_STATUS_UNKNOWN = "ACCOUNT_STATUS_UNKNOWN"
    ACCOUNT_STATUS_OPEN = "ACCOUNT_STATUS_OPEN"
    ACCOUNT_STATUS_CLOSED = "ACCOUNT_STATUS_CLOSED"
    ACCOUNT_STATUS_CANCELLED = "ACCOUNT_STATUS_CANCELLED"
    ACCOUNT_STATUS_PENDING_CLOSURE = "ACCOUNT_STATUS_PENDING_CLOSURE"
    ACCOUNT_STATUS_PENDING = "ACCOUNT_STATUS_PENDING"


class CalendarEventStatus(Enum):
    BOTH = "BOTH"
    ONLY_TRUE = "ONLY_TRUE"
    ONLY_FALSE = "ONLY_FALSE"


def create_customer(
    title="CUSTOMER_TITLE_MR",
    first_name="e2eTest",
    middle_name="",
    last_name="Smith",
    dob="1980-12-25",
    gender="CUSTOMER_GENDER_MALE",
    nationality="GB",
    email_address="e2etesting@tm.com",
    mobile_phone_number="+442079460536",
    home_phone_number="+442079460536",
    business_phone_number="+442079460536",
    contact_method="CUSTOMER_CONTACT_METHOD_NONE",
    country_of_residence="GB",
    country_of_taxation="GB",
    accessibility="CUSTOMER_ACCESSIBILITY_AUDIO",
    additional_details=None,
    details=None,
):
    datestr = datetime.now().strftime("%Y%m%d%H%M%S")
    randid = str(random.getrandbits(58))
    cust_id = datestr + randid[len(datestr) :]  # noqa: E203

    default_customer = {
        "request_id": uuid.uuid4().hex,
        "customer": {
            "id": cust_id,
            "status": "CUSTOMER_STATUS_ACTIVE",
            "identifiers": [{"identifier_type": "IDENTIFIER_TYPE_USERNAME", "identifier": cust_id}],
            "customer_details": {
                "title": title,
                "first_name": first_name,
                "middle_name": middle_name,
                "last_name": last_name,
                "dob": dob,
                "gender": gender,
                "nationality": nationality,
                "email_address": email_address,
                "mobile_phone_number": mobile_phone_number,
                "home_phone_number": home_phone_number,
                "business_phone_number": business_phone_number,
                "contact_method": contact_method,
                "country_of_residence": country_of_residence,
                "country_of_taxation": country_of_taxation,
                "accessibility": accessibility,
            },
            "additional_details": additional_details,
        },
    }

    customer_details = json.dumps(details if details else default_customer)
    customer = endtoend.helper.send_request("post", "/v1/customers", data=customer_details)

    log.info("Customer %s created", customer["id"])
    endtoend.testhandle.customers.append(customer["id"])
    return customer["id"]


def get_customer(customer_id):
    resp = endtoend.helper.send_request("get", "/v1/customers/" + customer_id)
    return resp


def get_existing_test_customer():
    if endtoend.testhandle.customers:
        return endtoend.testhandle.customers[0]
    else:
        return create_customer()


def set_customer_status(customer_id, status):
    post_body = {
        "request_id": uuid.uuid4().hex,
        "customer": {"status": status},
        "update_mask": {"paths": ["status"]},
    }

    resp = endtoend.helper.send_request(
        "put", "/v1/customers/" + customer_id, data=json.dumps(post_body)
    )
    log.info("Customer %s set to %s", customer_id, status)
    return resp


def get_customer_accounts(customer_id):
    resp = endtoend.helper.send_request(
        "get",
        "/v1/accounts",
        params={"stakeholder_id": customer_id, "page_size": "100"},
    )

    return resp["accounts"]


def get_customer_addresses(customer_id):
    body = {"customer_id": customer_id, "page_size": "1000", "include_previous": "True"}

    resp = endtoend.helper.send_request("get", "/v1/customer-addresses", params=body)

    # A list of customer addresses, ordered by descending creation time.
    return resp["customer_addresses"]


def create_payment_device(routing_info, status="PAYMENT_DEVICE_STATUS_ACTIVE"):
    post_body = {
        "payment_device": {"routing_info": routing_info, "status": status},
        "request_id": uuid.uuid4().hex,
    }

    resp = endtoend.helper.send_request("post", "/v1/payment-devices", data=json.dumps(post_body))

    return resp


def create_internal_account(
    request_id: str,
    internal_account_id: str,
    product_id: str,
    accounting_tside: str,
    permitted_denominations: list | None = None,
    details: dict[str, str] | None = None,
) -> dict[str, Any]:
    post_body = {
        "request_id": request_id,
        "internal_account": {
            "id": internal_account_id,
            "product_id": product_id,
            "permitted_denominations": permitted_denominations,
            "details": details,
            "accounting": {"tside": accounting_tside},
        },
    }

    resp = endtoend.helper.send_request("post", "/v1/internal-accounts", data=json.dumps(post_body))
    return resp


def create_payment_device_link(
    payment_device_id,
    account_id,
    token=None,
    status="PAYMENT_DEVICE_LINK_STATUS_ACTIVE",
):
    post_body = {
        "payment_device_link": {
            "token": token,
            "payment_device_id": payment_device_id,
            "account_id": account_id,
            "status": status,
        },
        "request_id": uuid.uuid4().hex,
    }

    resp = endtoend.helper.send_request(
        "post", "/v1/payment-device-links", data=json.dumps(post_body)
    )

    return resp


def get_payment_device_links(
    tokens=None,
    payment_device_ids=None,
    account_ids=None,
    effective_timestamp=None,
    include_inactive=None,
):
    # Returns a list of payment device links, or an empty list if none found.

    resp = endtoend.helper.send_request(
        "get",
        "/v1/payment-device-links",
        params={
            "tokens": tokens,
            "payment_device_ids": payment_device_ids,
            "account_ids": account_ids,
            "effective_timestamp": effective_timestamp,
            "include_inactive": include_inactive,
        },
    )

    return resp["payment_device_links"]


def get_payment_device(payment_device_ids):
    # If this ID doesn't exist, Vault will throw an error

    resp = endtoend.helper.send_request(
        "get", "/v1/payment-devices:batchGet", params={"ids": payment_device_ids}
    )

    return resp["payment_devices"][payment_device_ids]


def get_uk_acc_num_and_sort_code(account_id):
    pd_link = get_payment_device_links(account_ids=account_id)

    if len(pd_link) == 0:
        raise NameError("No payment device link found for " "account {}".format(account_id))

    # todo: Search through all pd_links
    pd = get_payment_device(pd_link[0]["payment_device_id"])

    if all(word in pd["routing_info"] for word in ["account_number", "bank_id"]):
        return pd["routing_info"]["account_number"], pd["routing_info"]["bank_id"]
    else:
        raise NameError(
            "No account number or sort code found for account "
            "{}. Has it been set up with UK routing info?".format(account_id)
        )


def create_flag_definition(
    flag_definition_id: str,
    name: str = "",
    description: str = "",
    required_flag_level: str = "FLAG_LEVEL_ACCOUNT",
    flag_visibility: str = "FLAG_VISIBILITY_CONTRACT",
) -> dict[str, str]:
    name = name or flag_definition_id
    description = description or flag_definition_id

    post_body = {
        "request_id": uuid.uuid4().hex,
        "flag_definition": {
            "id": flag_definition_id,
            "name": name,
            "description": description,
            "required_flag_level": required_flag_level,
            "flag_visibility": flag_visibility,
        },
    }

    resp = endtoend.helper.send_request("post", "/v1/flag-definitions", data=json.dumps(post_body))
    log.info(f"Flag definition created: {flag_definition_id}")
    return resp


def list_flag_definitions(
    flag_visibility: str = "FLAG_VISIBILITY_CONTRACT",
    flag_levels: list[str] | None = None,
    include_inactive: str = "true",
) -> list[dict[str, Any]]:
    body = {
        "flag_visibility_level": flag_visibility,
        "flag_levels": flag_levels or ["FLAG_LEVEL_ACCOUNT", "FLAG_LEVEL_CUSTOMER"],
        "include_inactive": include_inactive,
    }
    resp = endtoend.helper.list_resources("flag-definitions", params=body)
    return resp


def batch_get_flag_definitions(ids: list[str]) -> dict[str, dict[str, str]]:
    return endtoend.helper.send_request(
        "get", "/v1/flag-definitions:batchGet", params={"ids": ids}
    )["flag_definitions"]


def create_flag(
    flag_name: str,
    account_id: str | None = None,
    customer_id: str | None = None,
    payment_device_id: str | None = None,
    description: str | None = None,
):
    description = description or flag_name
    if account_id:
        target = "account_id"
        target_id = account_id
    elif customer_id:
        target = "customer_id"
        target_id = customer_id
    elif payment_device_id:
        target = "payment_device_id"
        target_id = payment_device_id
    else:
        raise NameError("No target has been specified so flag can not be applied!")

    post_body = {
        "request_id": uuid.uuid4().hex,
        "flag": {
            "flag_definition_id": flag_name,
            "description": description,
            target: target_id,
        },
    }

    resp = endtoend.helper.send_request("post", "/v1/flags", data=json.dumps(post_body))
    log.info(f"Flag applied for account {account_id}: {description}")
    return resp


def remove_flag(flag_id: str) -> dict[str, str]:
    put_body = {
        "request_id": uuid.uuid4().hex,
        "flag": {
            "is_active": False,
        },
        "update_mask": {"paths": ["is_active"]},
    }
    resp = endtoend.helper.send_request("put", f"/v1/flags/{flag_id}", data=json.dumps(put_body))
    log.info(f'Flag {flag_id} {resp["description"]} removed')
    return resp


def get_flag(flag_name: str, account_ids: list[str] | None = None) -> list[dict[str, Any]]:
    body = {"flag_definition_id": flag_name, "account_ids": account_ids or []}
    resp = endtoend.helper.list_resources("flags", params=body)
    return resp


def create_restriction_set_definition_version(
    restriction_set_definition_id: str,
    restriction_type: str,
    restriction_levels: list[str],
    description: str | None = None,
    request_id: str | None = None,
):
    description = description or restriction_set_definition_id

    post_body = {
        "request_id": request_id or uuid.uuid4().hex,
        "restriction_set_definition_version": {
            "restriction_set_definition_id": restriction_set_definition_id,
            "description": description,
            "restriction_definitions": [
                {
                    "restriction_type": restriction_type,
                    "required_restriction_levels": restriction_levels,
                }
            ],
        },
    }

    resp = endtoend.helper.send_request(
        "post",
        f"/v1/restriction-set-definition/{restriction_set_definition_id}/versions",
        data=json.dumps(post_body),
    )
    log.info(f"Restriction Set Definition created: {description}")
    return resp


def create_restriction_set(
    account_id: str, restriction_set_definition_id: str, name: str = "", description: str = ""
) -> dict:
    name = name or restriction_set_definition_id
    description = description or restriction_set_definition_id

    post_body = {
        "request_id": uuid.uuid4().hex,
        "restriction_set": {
            "restriction_set_definition_id": restriction_set_definition_id,
            "name": name,
            "description": description,
            "restriction_set_parameters": {},
            "account_id": account_id,
        },
    }

    resp = endtoend.helper.send_request("post", "/v1/restriction-sets", data=json.dumps(post_body))
    log.info(
        f"Restriction definition {restriction_set_definition_id} applied to account %s", account_id
    )
    return resp


def remove_restriction_set(account_id: str, restriction_set_id: str):
    resp = update_restriction_set(restriction_set_id, "is_active", False)
    log.info(f"Restriction set {restriction_set_id} removed from account {account_id}")
    return resp


def update_restriction_set(restriction_set_id: str, update_field: str, update_value: str):
    post_body = {
        "request_id": uuid.uuid4().hex,
        "restriction_set": {"id": restriction_set_id, update_field: update_value},
        "update_mask": {"paths": [update_field]},
    }

    resp = endtoend.helper.send_request(
        "put", "/v1/restriction-sets/" + restriction_set_id, data=json.dumps(post_body)
    )
    log.info(f"Restriction set {restriction_set_id} updated: {update_field} set to {update_value}")
    return resp


def get_account_schedule_assocs(account_id: str) -> list[dict[str, str]]:
    body = {
        "account_id": account_id,
    }
    resp = endtoend.helper.list_resources("account-schedule-assocs", params=body)

    # A list of account to schedule associations
    return resp


def batch_get_schedules(schedule_ids) -> dict[str, dict[str, str]]:
    body = {"ids": schedule_ids}

    resp = endtoend.helper.send_request("get", "/v1/schedules:batchGet", params=body)

    # A dict of schedule_id to schedule objects
    return resp["schedules"]


def get_jobs(schedule_id: str) -> list[dict[str, Any]]:
    """
    Gets all the jobs with the specified schedule_id
    :param schedule_id: id for filterling which jobs to retrieved.
    :return: list of schedules with the specified schedule_id else
    return empty list
    """
    body = {"schedule_id": schedule_id}
    return endtoend.helper.list_resources("jobs", params=body)


def get_plan_schedules(plan_id: str) -> list[dict[str, str]]:
    """
    Fetches all the schedules for a plan. The underlying endpoint only returns active schedules
    and there is no way to modify this behaviour
    """

    body = {"plan_id": plan_id}
    return endtoend.helper.list_resources("plan-schedules", page_size=20, params=body)


def get_account_derived_parameters(account_id: str, effective_timestamp: str = ""):
    body = {"fields_to_include": ["INCLUDE_FIELD_DERIVED_INSTANCE_PARAM_VALS"]}
    if effective_timestamp:
        body.update({"instance_param_vals_effective_timestamp": effective_timestamp})

    resp = endtoend.helper.send_request("get", f"/v1/accounts/{account_id}", params=body)

    return resp["derived_instance_param_vals"]


def get_live_balances(
    account_id: str,
) -> list[dict[str, str]]:
    params = {
        "account_ids": account_id,
    }

    return endtoend.helper.list_resources("balances/live", params)


def get_timerange_balances(
    account_id: str,
    from_value_time: datetime = None,
    to_value_time: datetime = None,
) -> list[dict[str, str]]:
    params = {
        "account_ids": account_id,
    }

    if from_value_time:
        params.update({"from_time": from_value_time.astimezone(timezone.utc).isoformat()})
    if to_value_time:
        params.update({"to_time": to_value_time.astimezone(timezone.utc).isoformat()})

    return endtoend.helper.list_resources("balances/timerange", params)


def get_account_update(account_update_id: str) -> dict[str, Any]:
    """
    Retrieve a specific account update by its id
    :param account_update_id: id of the account update to retrieve
    :return: the account update resource
    """

    resp = endtoend.helper.send_request("get", f"/v1/account-updates/{account_update_id}")

    return resp


def get_account_updates(account_id: str, statuses: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Get a list of account updates for a given account
    :param account_id: account id for the account to get updates for
    :param statuses: statuses of account updates to filter on. Optional.
    :return: list of account updates matching the criteria
    """

    params = {"account_id": account_id, "statuses": statuses}
    return endtoend.helper.list_resources("account-updates", params)


def get_account_updates_by_type(
    account_id: str, update_types: list[str], statuses: list[str] | None = None
) -> list[dict[str, Any]]:
    """
    Gets a list of account updates and filters by type
    :param account_id: the account id to get account updates for
    :param update_types: the list of account update types we want to filter for (not handled in API)
    :param statuses: the list of account update statuses we want to filter for (handled in API)
    :return: list of account updates
    """

    account_updates = get_account_updates(account_id, statuses)
    account_updates_by_type = [
        account_update
        for account_update in account_updates
        for update_type in update_types
        if update_type in account_update
    ]
    return account_updates_by_type


def get_product_version(product_version_id: str, include_code: bool = False) -> dict:
    """
    Fetches product version from instance.

    :param product_version_id: Instance version id of the product, not the id found in the sc file
    :param include_code: Specifies whether raw code needs to be included in response
    """
    view = ["PRODUCT_VERSION_VIEW_INCLUDE_CODE"] if include_code else []
    params = {"ids": product_version_id, "view": view}
    resp = endtoend.helper.send_request("get", "/v1/product-versions:batchGet", params=params)
    return resp["product_versions"][product_version_id]


def get_vault_version() -> Version:
    response = endtoend.helper.send_request("get", "/v1/vault-version")
    version: dict[str, Any] = response["version"]
    # As far as we know, major, minor, and patch are always integers.
    major: int = version["major"]
    minor: int = version["minor"]
    patch: int = version["patch"]
    label: str = version.get("label", "")
    return Version(f"{major}.{minor}.{patch}{label}")


def create_account_update(
    account_id: str,
    account_update: dict[str, dict[str, Any]],
    account_update_id: str = "",
) -> dict[str, Any]:
    """

    :param account_id: account id of the account to update
    :param account_update: dict where the key is the desired account update (i.e.
    instance_param_vals_update, product_version_update, activation_update, closure_update) and the
    value is the dict with the required parameters for the account update type. For example:
    {
        'instance_param_vals_update': {
            'instance_param_vals': {
                'KEY': 'value1'
            }
        }
    }
    :param account_update_id: optional account update id to use. Randomly generated by service if
    omitted
    :return: The resulting account update resource
    """

    body = {
        "request_id": uuid.uuid4().hex,
        "account_update": {
            "id": account_update_id,
            "account_id": account_id,
            **account_update,
        },
    }
    jsonbody = json.dumps(body)
    resp = endtoend.helper.send_request("post", "/v1/account-updates", data=jsonbody)
    log.info(f"Account update {account_update} created")
    return resp


def create_closure_update(account_id: str) -> dict[str, Any]:
    """
    Creates an account update to re-run the close_code hook once the account status is already
    'ACCOUNT_STATUS_PENDING_CLOSURE'
    :param account_id: the account id of the account to update
    :return: The resulting account update resource
    """
    account_update = {"closure_update": {}}
    return create_account_update(account_id, account_update)


def update_account_instance_parameters(
    account_id: str, instance_param_vals: dict[str, Any]
) -> dict[str, Any]:
    """
    Creates an account update to update specified instance parameters to the specified values
    :param account_id: the account id of the account to update
    :param instance_param_vals: dictionary of instance parameter names to updated values
    :return: The resulting account update resource
    """
    account_update = {"instance_param_vals_update": {"instance_param_vals": instance_param_vals}}
    return create_account_update(account_id, account_update)


def update_account(account_id: str, status: AccountStatus) -> dict[str, Any]:
    """
    Update an account
    :param account_id: account id of the account to update
    :param status: new account status
    :return: the updated account
    """
    body = {
        "request_id": str(uuid.uuid4()),
        "account": {"status": status.value},
        "update_mask": {"paths": ["status"]},
    }
    body = json.dumps(body)
    resp = endtoend.helper.send_request("put", "/v1/accounts/" + account_id, data=body)
    return resp


@retry_decorator(exceptions=(HTTPError), on_http_error_codes=[500, 503])
def create_product_version(
    request_id: str,
    code: str,
    product_id: str,
    supported_denominations: list[str],
    tags: list[str] | None = None,
    params: list[Any] | None = None,
    is_internal: bool = False,
    migration_strategy: str = "PRODUCT_VERSION_MIGRATION_STRATEGY_UNKNOWN",
    contract_properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Creates a product version by using the core api endpoint
    :param request_id: str, unique string ID that is used to ensure the request is idempotent
    :param code: str, the smart contract code
    :param product_id: str, the ID of the product we want to create
    :param supported_denominations: list[str], the denominations supported by this product version
    :param tags: list[str], tags for the product version
    :param params: list[object], the parameter values for the product version
    :param is_internal: bool, denotes if the product being uploaded is an internal product or not
    :param migration_strategy: str, the migration strategy for applying the new version
    :param contract_properties: dict[str, object], the contract specific property values
    :return: dict[str, object], return value of core api call
    """
    contract_properties = contract_properties or {}
    display_name = contract_properties.get("display_name", "")
    if is_internal:
        migration_strategy = "PRODUCT_VERSION_MIGRATION_STRATEGY_NEW_PRODUCT"

    post_body = {
        # ProductVersions are immutable, so we can use that to simply return an already created
        # ProductVersion.
        "request_id": request_id,
        "product_version": {
            "product_id": product_id,
            "code": code,
            "supported_denominations": supported_denominations,
            "params": params,
            "tags": tags or [],
            "display_name": display_name,
            "description": "",
            "summary": "",
        },
        "is_internal": is_internal,
        "migration_strategy": migration_strategy,
    }

    post_body = json.dumps(post_body)

    resp = endtoend.helper.send_request("post", "/v1/product-versions", data=post_body)

    return resp


def create_supervisor_contract(
    request_id: str,
    display_name: str,
):
    """
    Creates a supervisor contract. The core api behaviour means we create a product + product
    version in one API call, whereas supervisors contracts and supervisor contract versions are
    created in separate calls.
    :param request_id: str, unique string ID that is used to ensure the request is idempotent
    :param display_name: str, the human-readable name
    :return: dict[str, object], return value of core api call
    """
    post_body = {
        "request_id": request_id,
        "supervisor_contract": {
            "display_name": display_name,
        },
    }
    post_body = json.dumps(post_body)

    resp = endtoend.helper.send_request("post", "/v1/supervisor-contracts", data=post_body)

    return resp


def create_supervisor_contract_version(
    request_id: str,
    supervisor_contract_id: str,
    display_name: str,
    description: str,
    code: str,
):
    """
    Creates a supervisor contract version by using the core api endpoint
    :param request_id: str, unique string ID that is used to ensure the request is idempotent
    :param supervisor_contract_id: str, The ID of the SupervisorContract of which this is a version
    :param display_name: str, the human-readable name
    :param description: str, the human-readable description
    :param code: str, the smart contract code
    :return: dict[str, object], return value of core api call
    """
    post_body = {
        "request_id": request_id,
        "supervisor_contract_version": {
            "supervisor_contract_id": supervisor_contract_id,
            "display_name": display_name,
            "description": description,
            "code": code,
        },
    }
    post_body = json.dumps(post_body)

    resp = endtoend.helper.send_request("post", "/v1/supervisor-contract-versions", data=post_body)

    return resp


def create_account_schedule_tag(
    account_schedule_tag_id: str,
    description: str = "",
    sends_scheduled_operation_reports: bool = True,
    schedule_status_override: str = "ACCOUNT_SCHEDULE_TAG_SCHEDULE_STATUS_OVERRIDE_NO_OVERRIDE",
    schedule_status_override_start_timestamp: str | None = None,
    schedule_status_override_end_timestamp: str | None = None,
    test_pause_at_timestamp: str | None = None,
) -> dict[str, str]:
    post_body = {
        "request_id": str(uuid.uuid4()),
        "account_schedule_tag": {
            "id": account_schedule_tag_id,
            "description": description,
            "sends_scheduled_operation_reports": sends_scheduled_operation_reports,
            "schedule_status_override": schedule_status_override,
            "schedule_status_override_start_timestamp": schedule_status_override_start_timestamp,
            "schedule_status_override_end_timestamp": schedule_status_override_end_timestamp,
            "test_pause_at_timestamp": test_pause_at_timestamp,
        },
    }

    post_body = json.dumps(post_body)

    resp = endtoend.helper.send_request("post", "/v1/account-schedule-tags", data=post_body)

    return resp


def list_account_schedule_tags(result_limit: int) -> list[dict[str, str]]:
    return endtoend.helper.list_resources("account-schedule-tags", result_limit=result_limit)


def batch_get_account_schedule_tags(
    account_schedule_tag_ids: list[str],
) -> dict[str, dict[str, str]]:
    return endtoend.helper.send_request(
        "get",
        "/v1/account-schedule-tags:batchGet",
        params={"ids": account_schedule_tag_ids},
    )["account_schedule_tags"]


def update_account_schedule_tag(
    account_schedule_tag_id: str,
    schedule_status_override: str | None = None,
    schedule_status_override_start_timestamp: str | None = None,
    schedule_status_override_end_timestamp: str | None = None,
    test_pause_at_timestamp: str | None = None,
) -> dict[str, str]:
    update_mask_paths = list()
    account_schedule_tag = dict()

    # status, start timestamp and end timestamp must all be set together
    if schedule_status_override:
        update_mask_paths.extend(
            [
                "schedule_status_override",
                "schedule_status_override_start_timestamp",
                "schedule_status_override_end_timestamp",
            ]
        )
        account_schedule_tag.update(
            {
                "schedule_status_override": schedule_status_override,
                "schedule_status_override_start_timestamp": (
                    schedule_status_override_start_timestamp
                ),
                "schedule_status_override_end_timestamp": schedule_status_override_end_timestamp,
            }
        )

    if test_pause_at_timestamp:
        update_mask_paths.append("test_pause_at_timestamp")
        account_schedule_tag["test_pause_at_timestamp"] = test_pause_at_timestamp

    body = json.dumps(
        {
            "request_id": uuid.uuid4().hex,
            "account_schedule_tag": account_schedule_tag,
            "update_mask": {"paths": update_mask_paths},
        }
    )

    def result_wrapper(result_object: dict):
        transformed_result = {}
        for update_item in update_mask_paths:
            try:
                item_to_update = dateparser.parse(result_object.get(update_item)).isoformat()
            except (TypeError, ValueError):
                item_to_update = result_object.get(update_item)
            transformed_result.update({update_item: item_to_update})
        return transformed_result

    return endtoend.helper.retry_call(
        func=endtoend.helper.send_request,
        f_args=["put", "/v1/account-schedule-tags/" + account_schedule_tag_id, body],
        result_wrapper=result_wrapper,
        expected_result=account_schedule_tag,
        sleep_time=10,
        back_off=2,
        failure_message=f"Failed to update account schedule tag {account_schedule_tag_id} "
        f"using request {body}",
    )


def get_calendar_events(
    calendar_ids: list[str] | None = None,
    calendar_event_names: list[str] | None = None,
    calendar_timestamp_from: datetime | None = None,
    calendar_timestamp_to: datetime | None = None,
    active_calendar_event: CalendarEventStatus = CalendarEventStatus.ONLY_TRUE,
) -> list[dict[str, Any]]:
    body = {
        "calendar_ids": calendar_ids or [],
        "calendar_event_names": calendar_event_names or [],
        "calendar_timestamp_range.from": calendar_timestamp_from.isoformat()
        if calendar_timestamp_from
        else None,
        "calendar_timestamp_range.to": calendar_timestamp_to.isoformat()
        if calendar_timestamp_to
        else None,
        "active_calendar_event": active_calendar_event.value,
    }
    resp = endtoend.helper.list_resources("calendar-event", params=body)

    return resp


def create_calendar_event(
    calendar_id: str,
    start_timestamp: datetime,
    end_timestamp: datetime,
    name: str | None = None,
    event_id: str | None = None,
    is_active: bool = True,
):
    post_body = {
        "request_id": uuid.uuid4().hex,
        "calendar_event": {
            "id": event_id,
            "calendar_id": calendar_id,
            "name": name,
            "is_active": is_active,
            "start_timestamp": start_timestamp.isoformat(),
            "end_timestamp": end_timestamp.isoformat(),
        },
    }

    resp = endtoend.helper.send_request("post", "/v1/calendar-event", data=json.dumps(post_body))

    return resp


def list_calendars(
    order_by: str = "ORDER_BY_CREATE_TIMESTAMP_ASC",
    name_pattern_match_pattern: str | None = None,
    name_pattern_match_match_type: str = "MATCH_TYPE_UNKNOWN",
) -> list[dict[str, Any]]:
    body = {
        "order_by": order_by,
        "name_pattern_match.pattern": name_pattern_match_pattern,
        "name_pattern_match.match_type": name_pattern_match_match_type,
    }
    resp = endtoend.helper.list_resources("calendars", params=body)

    return resp


def create_calendar(
    calendar_id: str,
    is_active: bool = False,
    display_name: str = "",
    description: str = "",
) -> dict[str, str]:
    display_name = display_name or calendar_id
    description = description or calendar_id

    post_body = {
        "request_id": uuid.uuid4().hex,
        "calendar": {
            "id": calendar_id,
            "is_active": is_active,
            "display_name": display_name,
            "description": description,
        },
    }

    resp = endtoend.helper.send_request("post", "/v1/calendar", data=json.dumps(post_body))

    return resp


def update_calendar(
    calendar_id: str,
    is_active: bool | None = None,
    display_name: str | None = None,
    description: str | None = None,
) -> dict[str, str]:
    updated_fields = {}
    if is_active is not None:
        updated_fields["is_active"] = is_active
    if display_name is not None:
        updated_fields["display_name"] = display_name
    if description is not None:
        updated_fields["description"] = description

    post_body = {
        "request_id": uuid.uuid4().hex,
        "calendar": updated_fields,
        "update_mask": {"paths": list(updated_fields.keys())},
    }

    resp = endtoend.helper.send_request(
        "put", f"/v1/calendar/{calendar_id}:updateDetails", data=json.dumps(post_body)
    )

    return resp


def get_contract_modules() -> list[dict[str, Any]]:
    resp = endtoend.helper.list_resources("contract-modules", params=None)

    return resp


def get_contract_module_versions(
    contract_module_id: str = "",
) -> list[dict[str, Any]]:
    body = {
        "contract_module_id": contract_module_id,
    }
    resp = endtoend.helper.list_resources("contract-module-versions", params=body, page_size=10)

    return resp


def get_smart_contract_module_version_links(
    contract_version_id: str,
) -> list[dict[str, Any]]:
    resp = endtoend.helper.list_resources(
        "smart-contract-module-versions-links",
        params={"smart_contract_version_ids": contract_version_id},
    )

    return resp


def get_postings_api_client(
    client_id: str,
) -> dict[str, str]:
    return endtoend.helper.send_request("get", "/v1/postings-api-clients/" + client_id)


def create_postings_api_client(
    request_id: str,
    client_id: str,
    response_topic: str,
) -> dict[str, str]:
    post_body = {
        "request_id": request_id,
        "postings_api_client": {
            "id": client_id,
            "response_topic": response_topic,
        },
    }

    return endtoend.helper.send_request(
        "post", "/v1/postings-api-clients", data=json.dumps(post_body)
    )


def init_postings_api_client(
    client_id: str, response_topic: str, timeout: int = 5
) -> dict[str, str]:
    """
    Postings API client can be missing on the target instance (i.e. bootstrap job as part of DR)
    so ensure it's created if it cannot be found.
    """
    for i in range(timeout):
        try:
            return get_postings_api_client(client_id)
        except HTTPError as e:
            if "404" not in e.args[0]:
                if i < timeout:
                    time.sleep(1)
                    continue
                raise HTTPError(
                    "Unexpected error when trying to connect to endpoint /v1/postings-api-clients"
                ) from e

            log.info(
                "Could not find existing Postings API Client with ID: %s."
                "Creating new Postings API Client with above ID.",
                client_id,
            )
            return create_postings_api_client(
                request_id=str(uuid.uuid4()),
                client_id=client_id,
                response_topic=response_topic,
            )
