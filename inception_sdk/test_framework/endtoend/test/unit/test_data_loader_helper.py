# standard libs
from copy import deepcopy
from typing import Generator
from unittest import TestCase
from unittest.mock import Mock, patch

# inception sdk
import inception_sdk.test_framework.endtoend.data_loader_helper as data_loader_helper

TEST_DEPENDENCY_GROUPS = [
    {
        "instances": 3,
        "customer": {
            "id_base": 1000,
            "flags": [
                {"flag_definition_id": "CUSTOMER_FLAG_DEFINITION_1"},
                {"flag_definition_id": "CUSTOMER_FLAG_DEFINITION_2"},
            ],
        },
        "accounts": [
            {
                "account_opening_timestamp": "2020-01-01T00:00:00Z",
                "instance_param_vals": {
                    "loan_term": "2",
                    "loan_amount": "3000",
                    "gross_interest_rate": "0.098",
                    "repayment_day": "6",
                },
                "flags": [
                    {"flag_definition_id": "ACCOUNT_FLAG_DEFINITION_1"},
                    {"flag_definition_id": "ACCOUNT_FLAG_DEFINITION_2"},
                ],
            }
        ],
    }
]


def resource_extractors(
    request: dict,
) -> tuple[Generator, Generator, Generator, Generator]:

    customer_extractor = (
        resource
        for resource in request["resource_batch"]["resources"]
        if "customer_resource" in resource
    )
    account_extractor = (
        resource
        for resource in request["resource_batch"]["resources"]
        if "account_resource" in resource
    )
    customer_flag_extractor = (
        resource
        for resource in request["resource_batch"]["resources"]
        if "flag_resource" in resource and "customer_id" in resource["flag_resource"]
    )
    account_flag_extractor = (
        resource
        for resource in request["resource_batch"]["resources"]
        if "flag_resource" in resource and "account_id" in resource["flag_resource"]
    )

    return (
        customer_extractor,
        account_extractor,
        customer_flag_extractor,
        account_flag_extractor,
    )


class DataLoaderHelperTests(TestCase):
    def setUp(self) -> None:
        self.dependency_groups = deepcopy(TEST_DEPENDENCY_GROUPS)
        return super().setUp()

    def test_resource_ids_populated_with_customer_ids(self):

        customer_ids = []
        for (
            _,
            batch_resource_ids,
        ) in data_loader_helper.create_dataloader_resource_batch_requests(
            dependency_groups=self.dependency_groups,
            product_version_id="1",
        ):
            customer_ids.append(batch_resource_ids.customer_ids)

        self.assertListEqual(customer_ids, [["1000", "1001", "1002"]])

    def test_resource_ids_populated_with_account_ids(self):

        account_ids: list[list[str]] = []
        for (
            _,
            batch_resource_ids,
        ) in data_loader_helper.create_dataloader_resource_batch_requests(
            dependency_groups=self.dependency_groups,
            product_version_id="1",
        ):
            account_ids.append(
                [account_id.split("_", 1)[0] for account_id in batch_resource_ids.account_ids]
            )

        self.assertListEqual(account_ids, [["0", "1", "2"]])

    @patch.object(data_loader_helper, "get_flag_resource")
    def test_resource_ids_populated_with_customer_flag_ids(self, get_flag_resource: Mock):

        expected_customer_flag_ids = [
            "1000_CUSTOMER_FLAG_DEFINITION_1",
            "1000_CUSTOMER_FLAG_DEFINITION_2",
            "1001_CUSTOMER_FLAG_DEFINITION_1",
            "1001_CUSTOMER_FLAG_DEFINITION_2",
            "1002_CUSTOMER_FLAG_DEFINITION_1",
            "1002_CUSTOMER_FLAG_DEFINITION_2",
        ]
        # Flag ids are randomly generated, so we patch get_flag_resource to get around this
        get_flag_resource.side_effect = [{"id": id} for id in expected_customer_flag_ids]

        flag_ids = []
        self.dependency_groups[0]["accounts"][0]["flags"] = []
        for (
            _,
            batch_resource_ids,
        ) in data_loader_helper.create_dataloader_resource_batch_requests(
            dependency_groups=self.dependency_groups,
            product_version_id="1",
        ):
            flag_ids.extend(batch_resource_ids.flag_ids)

        self.assertListEqual(flag_ids, expected_customer_flag_ids)

    @patch.object(data_loader_helper, "get_flag_resource")
    def test_resource_ids_populated_with_account_flag_ids(self, get_flag_resource: Mock):

        expected_account_flag_ids = [
            "0_ACCOUNT_FLAG_DEFINITION_1",
            "0_ACCOUNT_FLAG_DEFINITION_2",
            "1_ACCOUNT_FLAG_DEFINITION_1",
            "1_ACCOUNT_FLAG_DEFINITION_2",
            "2_ACCOUNT_FLAG_DEFINITION_1",
            "2_ACCOUNT_FLAG_DEFINITION_2",
        ]
        # Flag ids are randomly generated, so we patch get_flag_resource to get around this
        get_flag_resource.side_effect = [{"id": id} for id in expected_account_flag_ids]

        flag_ids = []
        self.dependency_groups[0]["customer"]["flags"] = []
        for (
            _,
            batch_resource_ids,
        ) in data_loader_helper.create_dataloader_resource_batch_requests(
            dependency_groups=self.dependency_groups,
            product_version_id="1",
        ):
            flag_ids.extend(batch_resource_ids.flag_ids)

        self.assertListEqual(flag_ids, expected_account_flag_ids)

    @patch.object(data_loader_helper, "get_flag_resource")
    def test_resource_ids_segregated_by_batch(self, get_flag_resource: Mock):

        expected_account_flag_ids = [
            [
                "0_ACCOUNT_FLAG_DEFINITION_1",
                "0_ACCOUNT_FLAG_DEFINITION_2",
            ],
            [
                "1_ACCOUNT_FLAG_DEFINITION_1",
                "1_ACCOUNT_FLAG_DEFINITION_2",
            ],
            [
                "2_ACCOUNT_FLAG_DEFINITION_1",
                "2_ACCOUNT_FLAG_DEFINITION_2",
            ],
        ]

        # Flag ids are randomly generated, so we patch get_flag_resource to get around this
        get_flag_resource.side_effect = [
            {"id": id} for batch_flags in expected_account_flag_ids for id in batch_flags
        ]

        flag_ids = []
        self.dependency_groups[0]["customer"]["flags"] = []
        for (
            _,
            batch_resource_ids,
        ) in data_loader_helper.create_dataloader_resource_batch_requests(
            dependency_groups=self.dependency_groups,
            product_version_id="1",
            # The low batch size will result in multiple batches
            batch_size=3,
        ):
            flag_ids.append(batch_resource_ids.flag_ids)

        self.assertListEqual(flag_ids, expected_account_flag_ids)

    def test_batch_size_greater_than_batch_still_results_in_request(self):

        for (request, _,) in data_loader_helper.create_dataloader_resource_batch_requests(
            dependency_groups=self.dependency_groups,
            product_version_id="1",
            batch_size=1000,
        ):
            self.assertEqual(
                len(request["resource_batch"]["resources"]),
                18,
                "Expected 18 resources: 3* (1 customer, 2 customer flags, 1 account, 2 customer"
                " flags)",
            )

    def test_resources_from_same_instance_not_split_across_batches(self):

        for (request, _,) in data_loader_helper.create_dataloader_resource_batch_requests(
            dependency_groups=self.dependency_groups,
            product_version_id="1",
            batch_size=1,
        ):
            # Each batch has 1 customer, 2 customer flags, 1 account, 2 customer flags
            # despite batch_size = 1
            self.assertEqual(len(request["resource_batch"]["resources"]), 6)

    def test_resources_split_across_batches(self):

        all_requests = []
        for (request, _,) in data_loader_helper.create_dataloader_resource_batch_requests(
            dependency_groups=self.dependency_groups,
            product_version_id="1",
            # this batch size will result in two batches, one with 12 resources and the other 6
            batch_size=12,
        ):
            all_requests.append(request)

        batch_resource_counts = [
            len(request["resource_batch"]["resources"]) for request in all_requests
        ]
        self.assertListEqual(batch_resource_counts, [12, 6])

    def test_account_customer_dependencies_set_correctly(self):

        self.dependency_groups[0]["instances"] = 1
        self.dependency_groups[0]["customer"]["flags"] = []
        self.dependency_groups[0]["accounts"][0]["flags"] = []
        all_requests = []
        for (request, _,) in data_loader_helper.create_dataloader_resource_batch_requests(
            dependency_groups=self.dependency_groups,
            product_version_id="1",
        ):
            all_requests.append(request)

        customers, accounts, _, _ = resource_extractors(all_requests[0])
        customer_resource = next(customers)
        account_resource = next(accounts)

        self.assertListEqual([account_resource["id"]], customer_resource["dependencies"])
        self.assertListEqual([customer_resource["id"]], account_resource["dependencies"])

    def test_customer_flags_dependencies_set_correctly(self):

        self.dependency_groups[0]["instances"] = 1
        all_requests = []
        for (request, _,) in data_loader_helper.create_dataloader_resource_batch_requests(
            dependency_groups=self.dependency_groups,
            product_version_id="1",
        ):
            all_requests.append(request)

        customers, accounts, customer_flags, _ = resource_extractors(all_requests[0])
        customer_resource = next(customers)
        account_resource = next(accounts)
        customer_flag_1 = next(customer_flags)
        customer_flag_2 = next(customer_flags)

        self.assertListEqual(
            [customer_resource["id"]],
            customer_flag_1["dependencies"],
            "Customer flag should have a dependency on the customer",
        )
        self.assertListEqual(
            [customer_resource["id"]],
            customer_flag_2["dependencies"],
            "Customer flag should have a dependency on the customer",
        )
        self.assertListEqual(
            [customer_flag_1["id"], customer_flag_2["id"], account_resource["id"]],
            customer_resource["dependencies"],
            "Customer should have dependencies on both of its flags and the account",
        )

    def test_account_flags_dependencies_set_correctly(self):

        self.dependency_groups[0]["instances"] = 1
        all_requests = []
        for (request, _,) in data_loader_helper.create_dataloader_resource_batch_requests(
            dependency_groups=self.dependency_groups,
            product_version_id="1",
        ):
            all_requests.append(request)

        _, accounts, _, account_flags = resource_extractors(all_requests[0])

        account_resource = next(accounts)
        account_flag_1 = next(account_flags)
        account_flag_2 = next(account_flags)

        self.assertListEqual(
            [account_resource["id"]],
            account_flag_1["dependencies"],
            "Account flag should have a dependency on the account",
        )

        self.assertListEqual(
            [account_resource["id"]],
            account_flag_2["dependencies"],
            "Account flag should have a dependency on the account",
        )
        self.assertListEqual(
            ["1000", account_flag_1["id"], account_flag_2["id"]],
            account_resource["dependencies"],
            "Account should have dependencies on the customer and both of its flags",
        )
