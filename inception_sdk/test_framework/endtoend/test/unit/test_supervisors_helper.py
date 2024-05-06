# standard libs
import json
from unittest import TestCase
from unittest.mock import MagicMock, Mock, PropertyMock, mock_open, patch

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
import inception_sdk.test_framework.endtoend.supervisors_helper as supervisors_helper
from inception_sdk.common.python.file_utils import load_file_contents
from inception_sdk.test_framework.endtoend import core_api_helper

NORMAL_ASSOCIATIONS = (
    "inception_sdk/test_framework/endtoend/test/unit/input/normal_plan_associations.json"
)
MULTI_ASSOCIATIONS = (
    "inception_sdk/test_framework/endtoend/test/unit/input/multi_plan_associations.json"
)

EXAMPLE_SUPERVISOR_CONTENTS = load_file_contents(
    "inception_sdk/test_framework/common/tests/input/example_supervisor_contract.py"
)
EXPECTED_E2E_SUPERVISOR_CONTENTS = load_file_contents(
    "inception_sdk/test_framework/common/tests/output/supervisor_contract_supervisees_replaced.py"
)


class SupervisorsHelperTest(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with open(NORMAL_ASSOCIATIONS, "r", encoding="utf-8") as assoc_file:
            cls.normal_plan_associations = json.load(assoc_file)
        with open(MULTI_ASSOCIATIONS, "r", encoding="utf-8") as assoc_file:
            cls.multi_plan_associations = json.load(assoc_file)

    @patch.object(supervisors_helper, "get_plan_associations")
    def test_check_plan_associations_passes_with_list_input(self, get_plan_associations: Mock):

        get_plan_associations.return_value = self.normal_plan_associations

        expected_associations = [
            "a93de940-6300-a146-a71d-9b5389ee89a3",
            "1e3f7dfe-8f92-c2db-c62d-d58a6e6991f3",
            "22f72eed-9a16-7526-5fc3-8ff0278b8d62",
        ]
        try:
            supervisors_helper.check_plan_associations(
                self,
                plan_id="6f957686-05e8-2488-174a-63a11a460372",
                accounts=expected_associations,
            )
        except AssertionError as error:
            self.fail(f"Unexpected AssertionError raised: {error}")

    @patch.object(supervisors_helper, "get_plan_associations")
    def test_check_plan_associations_passes_with_dict_input(self, get_plan_associations: Mock):

        get_plan_associations.return_value = self.normal_plan_associations

        expected_associations = {
            "a93de940-6300-a146-a71d-9b5389ee89a3": "ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE",
            "1e3f7dfe-8f92-c2db-c62d-d58a6e6991f3": "ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE",
            "22f72eed-9a16-7526-5fc3-8ff0278b8d62": "ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE",
        }

        try:
            supervisors_helper.check_plan_associations(
                self,
                plan_id="6f957686-05e8-2488-174a-63a11a460372",
                accounts=expected_associations,
            )
        except AssertionError as error:
            self.fail(f"Unexpected AssertionError raised: {error}")

    @patch.object(supervisors_helper, "get_plan_associations")
    def test_check_plan_associations_fails_with_incorrect_status(self, get_plan_associations: Mock):

        get_plan_associations.return_value = self.normal_plan_associations

        expected_associations = {
            "a93de940-6300-a146-a71d-9b5389ee89a3": "ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE",
            "1e3f7dfe-8f92-c2db-c62d-d58a6e6991f3": "ACCOUNT_PLAN_ASSOC_STATUS_INACTIVE",
            "22f72eed-9a16-7526-5fc3-8ff0278b8d62": "ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE",
        }
        with self.assertRaises(AssertionError):
            supervisors_helper.check_plan_associations(
                self,
                plan_id="6f957686-05e8-2488-174a-63a11a460372",
                accounts=expected_associations,
            )

    @patch.object(supervisors_helper, "get_plan_associations")
    def test_check_plan_associations_fails_with_incorrect_account_id(
        self, get_plan_associations: Mock
    ):

        get_plan_associations.return_value = self.normal_plan_associations

        expected_associations = [
            "a93de940-6300-a146-a71d-9b5389ee89a3",
            "1e3f7dfe-8f92-c2db-c62d-d58a6e6991f3",
            "22f72eed-9a16-7526",
        ]
        with self.assertRaises(AssertionError):
            supervisors_helper.check_plan_associations(
                self,
                plan_id="6f957686-05e8-2488-174a-63a11a460372",
                accounts=expected_associations,
            )

    @patch.object(supervisors_helper, "get_plan_associations")
    def test_check_plan_associations_uses_latest_association(self, get_plan_associations: Mock):

        get_plan_associations.return_value = self.multi_plan_associations

        # the multiple associations has an active and inactive entry for 1e3f7...
        # as the inactive one comes last it's the only one that's preserved
        expected_associations = {
            "a93de940-6300-a146-a71d-9b5389ee89a3": "ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE",
            "1e3f7dfe-8f92-c2db-c62d-d58a6e6991f3": "ACCOUNT_PLAN_ASSOC_STATUS_INACTIVE",
            "22f72eed-9a16-7526-5fc3-8ff0278b8d62": "ACCOUNT_PLAN_ASSOC_STATUS_ACTIVE",
        }

        try:
            supervisors_helper.check_plan_associations(
                self,
                plan_id="6f957686-05e8-2488-174a-63a11a460372",
                accounts=expected_associations,
            )
        except AssertionError as error:
            self.fail(f"Unexpected AssertionError raised: {error}")

    @patch.object(supervisors_helper, "create_and_wait_for_plan_update")
    @patch.object(supervisors_helper, "get_plan_associations")
    def test_disassociate_account_from_plan(
        self, get_plan_associations: Mock, create_and_wait_for_plan_update: Mock
    ):

        get_plan_associations.return_value = [self.normal_plan_associations[0]]

        supervisors_helper.disassociate_account_from_plan(
            plan_id="6f957686-05e8-2488-174a-63a11a460372",
            account_id="22f72eed-9a16-7526-5fc3-8ff0278b8d62",
        )

        create_and_wait_for_plan_update.assert_called_once_with(
            plan_id="6f957686-05e8-2488-174a-63a11a460372",
            plan_action_type="disassociate_account_update",
            action={"account_plan_assoc_id": "5331bbea-ffe6-ed1e-da33-6574b126239e"},
        )

    @patch.object(supervisors_helper, "get_plan_updates")
    def test_get_plan_updates_by_type(self, mock_get_plan_updates: MagicMock):
        mock_get_plan_updates.return_value = [
            {"id": "1", "type_2": {}},
            {"id": "2", "type_1": {}},
            {"id": "3", "type_3": {}},
            {"id": "4", "type_1": {}},
        ]
        plan_updates = supervisors_helper.get_plan_updates_by_type(
            plan_id="my_plan", update_types=["type_1"], statuses=["status_1"]
        )
        self.assertListEqual(plan_updates, [{"id": "2", "type_1": {}}, {"id": "4", "type_1": {}}])

    @patch.object(supervisors_helper, "wait_for_plan_updates")
    @patch.object(endtoend.helper, "retry_call")
    def test_wait_for_plan_update_with_plan_update_id(
        self, mock_retry_call: MagicMock, mock_wait_for_plan_updates: MagicMock
    ):
        supervisors_helper.wait_for_plan_update(plan_update_id="update_id")
        mock_retry_call.assert_not_called()
        mock_wait_for_plan_updates.assert_called_once_with(
            plan_update_ids=["update_id"], target_status="PLAN_UPDATE_STATUS_COMPLETED"
        )

    @patch.object(supervisors_helper, "wait_for_plan_updates")
    @patch.object(endtoend.helper, "retry_call")
    def test_wait_for_plan_update_without_plan_update_id(
        self, mock_retry_call: MagicMock, mock_wait_for_plan_updates: MagicMock
    ):
        mock_retry_call.return_value = [{"id": "update_id"}]
        supervisors_helper.wait_for_plan_update(
            plan_id="plan_id", plan_update_type="activation_update"
        )
        mock_wait_for_plan_updates.assert_called_once_with(
            plan_update_ids=["update_id"], target_status="PLAN_UPDATE_STATUS_COMPLETED"
        )


class UpdateSupervisorContractTest(TestCase):
    maxDiff = None

    @patch.object(endtoend, "testhandle")
    @patch("builtins.open", mock_open(read_data=EXAMPLE_SUPERVISOR_CONTENTS))
    @patch.object(core_api_helper, "create_supervisor_contract_version")
    @patch.object(core_api_helper, "create_supervisor_contract")
    def test_external_resource_ids_updated(
        self,
        mock_create_supervisor_contract: MagicMock,
        mock_create_supervisor_contract_version: MagicMock,
        mock_testhandle: MagicMock,
    ):
        type(mock_testhandle).default_paused_tag_id = PropertyMock(return_value="E2E_PAUSED_TAG")
        type(mock_testhandle).controlled_schedule_tags = PropertyMock(
            return_value={"TEST_CONTRACT": {"EVENT_WITH_SINGLE_TAG": "E2E_AST_1"}}
        )
        type(mock_testhandle).clu_reference_mappings = PropertyMock(
            return_value={
                # Supervisee contract version ids
                "us_checking_account": "us_checking_account_ver_id",
                "us_savings_account": "us_savings_account_ver_id",
            },
        )
        supervisors_helper.upload_supervisor_contracts(
            supervisor_contracts={"TEST_CONTRACT": {"path": "dummy_path"}}
        )

        updated_supervisor_contract = mock_create_supervisor_contract_version.call_args_list[
            0
        ].kwargs["code"]
        self.assertEqual(updated_supervisor_contract, EXPECTED_E2E_SUPERVISOR_CONTENTS)
