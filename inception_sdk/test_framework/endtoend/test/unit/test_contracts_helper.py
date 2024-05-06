# standard libs
import json
from typing import Callable
from unittest import TestCase
from unittest.mock import MagicMock, Mock, PropertyMock, mock_open, patch, sentinel

# third party
import requests

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.common.python.file_utils import load_file_contents
from inception_sdk.common.test.mocks.kafka import MockConsumer, MockMessage
from inception_sdk.test_framework.endtoend import contracts_helper, core_api_helper
from inception_sdk.test_framework.endtoend.contracts_helper import (
    COMMON_ACCOUNT_SCHEDULE_TAG_PATH,
    ContractNotificationResourceType,
    SetupError,
    get_contract_content_for_e2e,
    prepare_parameters_for_e2e,
)

EXAMPLE_CONTRACT_CONTENTS = load_file_contents(
    "inception_sdk/test_framework/common/tests/input/example_contract.py"
)
EXPECTED_E2E_CONTRACT_CONTENTS = load_file_contents(
    "inception_sdk/test_framework/common/tests/output/contract_clu_references_replaced.py"
)

EXAMPLE_RENDERED_TEMPLATE = load_file_contents(
    "inception_sdk/test_framework/endtoend/test/unit/input/dummy_rendered_template.txt"
)
EXAMPLE_CONTRACT_NOTIFICATION = load_file_contents(
    "inception_sdk/test_framework/endtoend/test/unit/input/contract_notification.json"
)
EXPECTED_EVENT_TYPES = load_file_contents(
    "inception_sdk/test_framework/endtoend/test/unit/output/event_types.txt"
)


class TestContractsHelper(TestCase):
    test_product_id = "test_product_id"

    @patch.object(contracts_helper, "SmartContractRenderer")
    @patch.object(contracts_helper, "RendererConfig")
    @patch.object(contracts_helper, "is_file_renderable")
    @patch.object(contracts_helper, "load_module_from_filepath", MagicMock)
    def test_renderer_called_if_source_contract_is_renderable(
        self,
        mock_is_file_renderable: Mock,
        mock_renderer_config: Mock,
        mock_renderer: Mock,
    ):
        test_contract_properties = {
            "path": "test_contract_template_filepath",
            "template_params": {},
        }

        expected_content = "expected_content"

        mock_renderer_instance = Mock()
        mock_renderer.return_value = mock_renderer_instance
        mock_renderer_instance.rendered_contract = expected_content
        mock_is_file_renderable.return_value = True

        actual_content = get_contract_content_for_e2e(
            self.test_product_id, test_contract_properties
        )
        mock_renderer_config.assert_called_once_with(
            autogen_warning="# Code auto-generated for e2e testing",
            apply_formatting=False,
            use_git=False,
        )
        mock_renderer.assert_called_once()
        mock_renderer_instance.render.assert_called_once_with(write_to_file=False)
        self.assertEqual(actual_content, expected_content)

    @patch("inception_sdk.test_framework.endtoend.contracts_helper.SmartContractRenderer")
    @patch("inception_sdk.test_framework.endtoend.contracts_helper.RendererConfig")
    @patch("inception_sdk.test_framework.endtoend.contracts_helper.load_file_contents")
    def test_renderer_not_called_if_source_contract_absent(
        self, mock_load_file_contents_method: Mock, mock_renderer_config: Mock, mock_renderer: Mock
    ):
        expected_content = "expected_content"

        test_contract_properties = {
            "path": "path_to/test_contract.py",
            "template_params": {},
        }

        mock_renderer_instance = Mock()
        mock_renderer.return_value = mock_renderer_instance
        mock_load_file_contents_method.return_value = expected_content

        actual_content = get_contract_content_for_e2e(
            self.test_product_id, test_contract_properties
        )

        mock_renderer_config.assert_not_called()
        mock_renderer.assert_not_called()
        mock_renderer_instance.render.assert_not_called()

        self.assertEqual(actual_content, expected_content)

    def test_error_raised_if_neither_path_nor_source_are_provided(self):
        test_contract_properties = {
            "template_params": {},
        }
        with self.assertRaises(NameError) as e:
            get_contract_content_for_e2e(self.test_product_id, test_contract_properties)

        self.assertIn(
            "was not specified with a valid 'path' property",
            str(e.exception),
        )

    @patch.dict(
        "inception_sdk.test_framework.endtoend.testhandle.kafka_consumers",
        {
            contracts_helper.CONTRACT_NOTIFICATIONS_TOPIC: MockConsumer(
                [MockMessage(value=EXAMPLE_CONTRACT_NOTIFICATION)]
            )
        },
    )
    def test_wait_for_contract_notification_with_match(self):
        result = contracts_helper.wait_for_contract_notification(
            notification_type="my_notification_type",
            notification_details={"key": "value"},
            resource_id="my_resource_id",
            resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )
        self.assertIsNone(result)

    @patch.dict(
        "inception_sdk.test_framework.endtoend.testhandle.kafka_consumers",
        {
            contracts_helper.CONTRACT_NOTIFICATIONS_TOPIC: MockConsumer(
                [MockMessage(value=EXAMPLE_CONTRACT_NOTIFICATION)]
            )
        },
    )
    @patch.object(
        contracts_helper,
        "wait_for_messages",
        Mock(return_value={"another_resource_id_my_notification_type": None}),
    )
    def test_wait_for_contract_notification_with_no_match(self):
        with self.assertRaises(Exception) as e:
            contracts_helper.wait_for_contract_notification(
                notification_type="my_notification_type",
                notification_details={"key": "value"},
                resource_id="another_resource_id",
                resource_type=ContractNotificationResourceType.RESOURCE_ACCOUNT,
            )
        self.assertEqual(
            e.exception.args[0],
            "Failed to retrieve 1 notifications "
            "with following id and type: another_resource_id_my_notification_type",
        )


class UpdateContractTest(TestCase):
    maxDiff = None

    @patch.object(endtoend, "testhandle")
    @patch("builtins.open", mock_open(read_data=EXAMPLE_CONTRACT_CONTENTS))
    @patch.object(endtoend.core_api_helper, "create_product_version")
    def test_external_resource_ids_updated(
        self, create_product_version_mock: Mock, mock_testhandle: MagicMock
    ):
        type(mock_testhandle).default_paused_tag_id = PropertyMock(return_value="E2E_PAUSED_TAG")
        type(mock_testhandle).controlled_schedule_tags = PropertyMock(
            return_value={"TEST_CONTRACT": {"EVENT_WITH_SINGLE_TAG": "E2E_AST_1"}}
        )
        type(mock_testhandle).clu_reference_mappings = PropertyMock(
            return_value={
                # Calendar Id
                "CALENDAR_1": "E2E_CALENDAR_1",
                "CALENDAR_2": "E2E_CALENDAR_2",
                "CALENDAR_3": "E2E_CALENDAR_3",
                # Flag Definition Id
                "ACCOUNT_DORMANT": "E2E_ACCOUNT_DORMANT",
                "REPAYMENT_HOLIDAY": "E2E_REPAYMENT_HOLIDAY",
            },
        )

        contracts_helper.upload_contracts(
            contracts={"TEST_CONTRACT": {"path": "dummy_path", "template_params": {}}}
        )
        updated_contract = create_product_version_mock.call_args_list[0].kwargs["code"]
        self.assertEqual(updated_contract, EXPECTED_E2E_CONTRACT_CONTENTS)


class UpdateRenderedContractTest(TestCase):
    @patch.object(endtoend, "testhandle")
    @patch.object(contracts_helper, "SmartContractRenderer")
    @patch.object(endtoend.core_api_helper, "create_product_version")
    def test_event_types_replaced_with_repr(
        self,
        mock_create_product_version: MagicMock,
        mock_renderer: MagicMock,
        mock_testhandle: MagicMock,
    ) -> None:
        mock_renderer_instance = Mock()
        # The contents of this contract won't affect event type output as we replace the template's
        # event_types with repr and insert this into the rendered contract
        mock_renderer_instance.rendered_contract = EXAMPLE_RENDERED_TEMPLATE
        mock_renderer.return_value = mock_renderer_instance

        type(mock_testhandle).default_paused_tag_id = PropertyMock(return_value="E2E_PAUSED_TAG")
        type(mock_testhandle).controlled_schedule_tags = PropertyMock(
            return_value={
                "TEST_CONTRACT": {
                    "event_type_1": "PAUSED_DUMMY_event_type_1_tag_1",
                    "event_type_4": "PAUSED_DUMMY_event_type_4_tag_1",
                }
            }
        )

        contracts_helper.upload_contracts(
            contracts={
                "TEST_CONTRACT": {
                    "path": "inception_sdk/test_framework/endtoend/test/unit/input/"
                    "dummy_template.py",
                    "template_params": {},
                }
            }
        )

        updated_contract = mock_create_product_version.call_args_list[0].kwargs["code"]

        self.assertRegex(updated_contract, r"event_types_E2E_.* = dummy_feature_get_event_types")
        self.assertIn(
            EXPECTED_EVENT_TYPES,
            updated_contract,
        )


@patch.object(contracts_helper.uuid, "uuid4")
@patch.object(endtoend.core_api_helper, "create_account_schedule_tag")
@patch.object(endtoend, "testhandle")
class CreateAccountScheduleTagsTest(TestCase):
    maxDiff = None

    def create_account_schedule_tags(self) -> Callable[..., dict[str, str]]:
        return lambda account_schedule_tag_id, **kwargs: {
            "id": f"{account_schedule_tag_id}_uploaded_tag"
        }

    def test_only_create_default_paused_tag_if_no_controlled_schedules(
        self,
        mock_testhandle: MagicMock,
        mock_create_account_schedule_tag: MagicMock,
        mock_uuid4: MagicMock,
    ):
        mock_create_account_schedule_tag.return_value = {"id": "uploaded_id"}

        contracts_helper.create_account_schedule_tags(controlled_schedules={})

        self.assertDictEqual(mock_testhandle.controlled_schedule_tags, {})
        self.assertEquals(mock_testhandle.default_paused_tag_id, "uploaded_id")

    def test_only_create_default_paused_tag_if_upgrades_but_no_controlled_schedules(
        self,
        mock_testhandle: MagicMock,
        mock_create_account_schedule_tag: MagicMock,
        mock_uuid4: MagicMock,
    ):
        mock_create_account_schedule_tag.return_value = {"id": "uploaded_id"}
        mock_testhandle.CONTRACT_VERSION_UPGRADES = {"from_product": "to_product"}
        contracts_helper.create_account_schedule_tags(controlled_schedules={})

        self.assertDictEqual(mock_testhandle.controlled_schedule_tags, {})
        self.assertEquals(mock_testhandle.default_paused_tag_id, "uploaded_id")

    def test_create_tags_for_controlled_schedules(
        self,
        mock_testhandle: MagicMock,
        mock_create_account_schedule_tag: MagicMock,
        mock_uuid4: MagicMock,
    ):
        mock_create_account_schedule_tag.side_effect = self.create_account_schedule_tags()
        mock_uuid4.side_effect = ["uuid_1", "uuid_2", "uuid_3", "uuid_4"]

        contracts_helper.create_account_schedule_tags(
            controlled_schedules={
                "product_1": ["schedule_1", "schedule_2"],
                "product_2": ["schedule_1"],
            }
        )

        self.assertDictEqual(
            mock_testhandle.controlled_schedule_tags,
            {
                "product_1": {
                    "schedule_1": "PAUSED_E2E_TAG_schedule_1_uuid_1_uploaded_tag",
                    "schedule_2": "PAUSED_E2E_TAG_schedule_2_uuid_2_uploaded_tag",
                },
                "product_2": {"schedule_1": "PAUSED_E2E_TAG_schedule_1_uuid_3_uploaded_tag"},
            },
        )
        self.assertEquals(
            mock_testhandle.default_paused_tag_id, "PAUSED_E2E_TAG_DEFAULT_uuid_4_uploaded_tag"
        )

    def test_upgraded_products_preserve_schedule_tags_by_default(
        self,
        mock_testhandle: MagicMock,
        mock_create_account_schedule_tag: MagicMock,
        mock_uuid4: MagicMock,
    ):
        mock_create_account_schedule_tag.side_effect = self.create_account_schedule_tags()
        mock_uuid4.side_effect = ["uuid_1", "uuid_2", "uuid_3"]
        mock_testhandle.CONTRACT_VERSION_UPGRADES = {"from_product": "to_product"}
        contracts_helper.create_account_schedule_tags(
            controlled_schedules={
                "from_product": ["schedule_1", "schedule_2"],
            }
        )

        expected_product_schedule_tags = {
            "schedule_1": "PAUSED_E2E_TAG_schedule_1_uuid_1_uploaded_tag",
            "schedule_2": "PAUSED_E2E_TAG_schedule_2_uuid_2_uploaded_tag",
        }

        self.assertDictEqual(
            mock_testhandle.controlled_schedule_tags,
            {
                "from_product": expected_product_schedule_tags,
                "to_product": expected_product_schedule_tags,
            },
        )
        self.assertEquals(
            mock_testhandle.default_paused_tag_id, "PAUSED_E2E_TAG_DEFAULT_uuid_3_uploaded_tag"
        )

    def test_upgraded_products_schedules_can_still_be_controlled_separately(
        self,
        mock_testhandle: MagicMock,
        mock_create_account_schedule_tag: MagicMock,
        mock_uuid4: MagicMock,
    ):
        mock_create_account_schedule_tag.side_effect = self.create_account_schedule_tags()
        mock_uuid4.side_effect = ["uuid_1", "uuid_2", "uuid_3", "uuid_4"]
        mock_testhandle.CONTRACT_VERSION_UPGRADES = {"from_product": "to_product"}
        # We expect schedule 2's tag to be preserved on to_product, but not schedule 1's
        contracts_helper.create_account_schedule_tags(
            controlled_schedules={
                "from_product": ["schedule_1", "schedule_2"],
                "to_product": ["schedule_1"],
            }
        )

        self.assertDictEqual(
            mock_testhandle.controlled_schedule_tags,
            {
                "from_product": {
                    "schedule_1": "PAUSED_E2E_TAG_schedule_1_uuid_1_uploaded_tag",
                    "schedule_2": "PAUSED_E2E_TAG_schedule_2_uuid_2_uploaded_tag",
                },
                "to_product": {
                    "schedule_1": "PAUSED_E2E_TAG_schedule_1_uuid_3_uploaded_tag",
                    "schedule_2": "PAUSED_E2E_TAG_schedule_2_uuid_2_uploaded_tag",
                },
            },
        )
        self.assertEquals(
            mock_testhandle.default_paused_tag_id, "PAUSED_E2E_TAG_DEFAULT_uuid_4_uploaded_tag"
        )

    @patch.object(endtoend.core_api_helper, "batch_get_account_schedule_tags")
    def test_create_tags_with_conflicting_previously_updated_tag(
        self,
        mock_batch_get_account_schedule_tags: MagicMock,
        mock_testhandle: MagicMock,
        mock_create_account_schedule_tag: MagicMock,
        mock_uuid4: MagicMock,
    ):
        mock_create_account_schedule_tag.side_effect = requests.HTTPError(
            "409 Client Error: Conflict"
        )
        mock_batch_get_account_schedule_tags.return_value = {}
        mock_uuid4.side_effect = ["uuid_1", "uuid_2", "uuid_3", "uuid_4"]

        with self.assertRaisesRegex(ValueError, r"Found existing tag"):
            contracts_helper.create_account_schedule_tags(
                controlled_schedules={"product_1": ["schedule_1"]}
            )

    @patch.object(endtoend.core_api_helper, "batch_get_account_schedule_tags")
    def test_create_tags_with_matching_previously_updated_tag(
        self,
        mock_batch_get_account_schedule_tags: MagicMock,
        mock_testhandle: MagicMock,
        mock_create_account_schedule_tag: MagicMock,
        mock_uuid4: MagicMock,
    ):
        # Ensure first attempt fails
        mock_create_account_schedule_tag.side_effect = [
            requests.HTTPError("409 Client Error: Conflict"),
            {"id": "PAUSED_E2E_TAG_DEFAULT_uuid_2_uploaded_tag"},
        ]
        mock_batch_get_account_schedule_tags.return_value = {
            "PAUSED_E2E_TAG_schedule_1_uuid_1": contracts_helper.extract_resource(
                COMMON_ACCOUNT_SCHEDULE_TAG_PATH, "account_schedule_tag"
            )
        }
        mock_uuid4.side_effect = ["uuid_1", "uuid_2"]

        contracts_helper.create_account_schedule_tags(
            controlled_schedules={"product_1": ["schedule_1"]}
        )

        self.assertDictEqual(
            mock_testhandle.controlled_schedule_tags,
            {
                "product_1": {
                    # This the id from the default tag, as per
                    # mock_batch_get_account_schedule_tags.return_value
                    "schedule_1": "PAUSED_E2E_TAG",
                },
            },
        )
        self.assertEquals(
            mock_testhandle.default_paused_tag_id, "PAUSED_E2E_TAG_DEFAULT_uuid_2_uploaded_tag"
        )

    def test_create_tags_with_unknown_error(
        self,
        mock_testhandle: MagicMock,
        mock_create_account_schedule_tag: MagicMock,
        mock_uuid4: MagicMock,
    ):
        mock_create_account_schedule_tag.side_effect = Exception("Unknown")
        mock_uuid4.side_effect = ["uuid_1", "uuid_2", "uuid_3", "uuid_4"]

        with self.assertRaises(Exception) as ctx:
            contracts_helper.create_account_schedule_tags(
                controlled_schedules={"product_1": ["schedule_1"]}
            )
        self.assertEquals(ctx.exception.args[0], "Unknown")


class CreateContractNotificationTest(TestCase):
    @patch.object(contracts_helper.uuid, "uuid4")
    @patch.object(contracts_helper, "produce_message")
    @patch.object(endtoend.testhandle, "kafka_producer")
    def test_create_contract_notification(
        self, mock_producer: MagicMock, mock_produce_message: MagicMock, mock_uuid_4: MagicMock
    ):
        # we're ultimately mocking uuid.uuid4().hex, so we need uuid.uuid() to return a mock
        # with a property mock for the .hex property
        # can't use sentinels because they're not json serialisable
        mock_uuid = MagicMock()
        type(mock_uuid).hex = PropertyMock(return_value="my_uuid")
        mock_uuid_4.return_value = mock_uuid

        contracts_helper.send_contract_notification(
            notification_details={"my": "details"},
            notification_type="type",
            resource_id="id",
            resource_type=contracts_helper.ContractNotificationResourceType.RESOURCE_ACCOUNT,
        )

        mock_uuid_4.assert_called_once()
        mock_produce_message.assert_called_once_with(
            mock_producer,
            contracts_helper.CONTRACT_NOTIFICATIONS_TOPIC,
            json.dumps(
                {
                    "event_id": "my_uuid",
                    "notification_type": "type",
                    "resource_id": "id",
                    "resource_type": (
                        contracts_helper.ContractNotificationResourceType.RESOURCE_ACCOUNT.value
                    ),
                    "notification_details": {"my": "details"},
                }
            ),
        )


@patch.dict(
    "inception_sdk.test_framework.endtoend.testhandle.internal_contract_pid_to_uploaded_pid",
    {sentinel.contract: sentinel.product_id},
)
# @patch.dict("inception_sdk.test_framework.endtoend.testhandle.internal_account_id_to_uploaded_id")
@patch.object(core_api_helper, "create_internal_account")
class CreateInternalAccountTest(TestCase):
    maxDiff = None

    def test_create_internal_account_with_composite_id_over_length_limit(
        self, mock_create_internal_account: MagicMock
    ):
        with self.assertRaises(SetupError) as e:
            contracts_helper.create_internal_account(
                account_id="TEST_INTERNAL_NAME_OVER_30_CHARS",
                contract=sentinel.contract,
                accounting_tside="TSIDE_ASSET",
                details=sentinel.details,
            )

        self.assertIn(
            "Internal account id e2e_A_TEST_INTERNAL_NAME_OVER_30_CHARS is longer than 36 "
            "characters.",
            str(e.exception),
        )

        mock_create_internal_account.assert_not_called()

    def test_create_internal_account_without_composite_id_over_length_limit(
        self, mock_create_internal_account: MagicMock
    ):
        with self.assertRaises(SetupError) as e:
            contracts_helper.create_internal_account(
                account_id="TEST_INTERNAL_NAME_OVER_36_CHARS12345",
                contract=sentinel.contract,
                accounting_tside="TSIDE_ASSET",
                details=sentinel.details,
                use_composite_id=False,
            )

        self.assertIn(
            "Internal account id TEST_INTERNAL_NAME_OVER_36_CHARS12345 is longer than 36 "
            "characters.",
            str(e.exception),
        )

        mock_create_internal_account.assert_not_called()

    @patch.dict(
        "inception_sdk.test_framework.endtoend.testhandle.internal_account_id_to_uploaded_id", {}
    )
    def test_create_internal_account_under_length_limit_with_composite_id(
        self, mock_create_internal_account: MagicMock
    ):
        mock_create_internal_account.return_value = sentinel.account
        result = contracts_helper.create_internal_account(
            account_id="TEST_INTERNAL_NAME_EQUAL_MAX_L",
            contract=sentinel.contract,
            accounting_tside="TSIDE_ASSET",
            details=sentinel.details,
        )
        self.assertEqual(result, sentinel.account)
        mock_create_internal_account.assert_called_once_with(
            request_id="e2e_A_TEST_INTERNAL_NAME_EQUAL_MAX_L",
            internal_account_id="e2e_A_TEST_INTERNAL_NAME_EQUAL_MAX_L",
            product_id=sentinel.product_id,
            accounting_tside="TSIDE_ASSET",
            details=sentinel.details,
        )
        self.assertDictEqual(
            endtoend.testhandle.internal_account_id_to_uploaded_id,
            {"TEST_INTERNAL_NAME_EQUAL_MAX_L": "e2e_A_TEST_INTERNAL_NAME_EQUAL_MAX_L"},
        )

    @patch.dict(
        "inception_sdk.test_framework.endtoend.testhandle.internal_account_id_to_uploaded_id", {}
    )
    def test_create_internal_account_under_length_limit_without_composite_id(
        self,
        mock_create_internal_account: MagicMock,
    ):
        mock_create_internal_account.return_value = sentinel.account
        result = contracts_helper.create_internal_account(
            account_id="TEST_INTERNAL_NAME_EQUAL_MAX_L",
            contract=sentinel.contract,
            accounting_tside="TSIDE_ASSET",
            details=sentinel.details,
            use_composite_id=False,
        )
        self.assertEqual(result, sentinel.account)
        mock_create_internal_account.assert_called_once_with(
            request_id="TEST_INTERNAL_NAME_EQUAL_MAX_L",
            internal_account_id="TEST_INTERNAL_NAME_EQUAL_MAX_L",
            product_id=sentinel.product_id,
            accounting_tside="TSIDE_ASSET",
            details=sentinel.details,
        )
        self.assertDictEqual(
            endtoend.testhandle.internal_account_id_to_uploaded_id,
            {"TEST_INTERNAL_NAME_EQUAL_MAX_L": "TEST_INTERNAL_NAME_EQUAL_MAX_L"},
        )


class PrepareParametersForE2ETest(TestCase):
    parameters = {
        "param_1": "value_1",
        "param_2": "value_2",
        "param_3": {"key_1": "value_1", "key_2": "value_2"},
    }

    def test_handle_internal_account_parameters(self):
        self.assertDictEqual(
            prepare_parameters_for_e2e(
                parameters=self.parameters,
                internal_account_param_mapping={"param_1": "e2e_value_1"},
            ),
            {
                "param_1": {"internal_account_key": "e2e_value_1"},
                "param_2": "value_2",
                "param_3": {"key_1": "value_1", "key_2": "value_2"},
            },
        )

    def test_handle_flag_parameters(self):
        self.assertDictEqual(
            prepare_parameters_for_e2e(
                parameters=self.parameters,
                flag_param_mapping={"param_2": ["e2e_value_2"]},
            ),
            {
                "param_1": "value_1",
                "param_2": {"flag_key": ["e2e_value_2"]},
                "param_3": {"key_1": "value_1", "key_2": "value_2"},
            },
        )

    def test_handle_nested_internal_account_parameters(self):
        self.assertDictEqual(
            prepare_parameters_for_e2e(
                parameters=self.parameters,
                nested_internal_account_param_mapping={
                    "param_3": {"key_1": "e2e_value_1", "key_2": "e2e_value_2"}
                },
            ),
            {
                "param_1": "value_1",
                "param_2": "value_2",
                "param_3": {
                    "nested_internal_account_keys": {
                        "key_1": {"internal_account_key": "e2e_value_1"},
                        "key_2": {"internal_account_key": "e2e_value_2"},
                    }
                },
            },
        )

    def test_handle_mixture_of_parameters(self):
        self.assertDictEqual(
            prepare_parameters_for_e2e(
                parameters=self.parameters,
                internal_account_param_mapping={"param_1": "e2e_value_1"},
                nested_internal_account_param_mapping={
                    "param_3": {"key_1": "e2e_value_1", "key_2": "e2e_value_2"}
                },
                flag_param_mapping={"param_2": ["e2e_value_2"]},
            ),
            {
                "param_1": {"internal_account_key": "e2e_value_1"},
                "param_2": {"flag_key": ["e2e_value_2"]},
                "param_3": {
                    "nested_internal_account_keys": {
                        "key_1": {"internal_account_key": "e2e_value_1"},
                        "key_2": {"internal_account_key": "e2e_value_2"},
                    }
                },
            },
        )
