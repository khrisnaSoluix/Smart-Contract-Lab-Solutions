# standard libs
import json
from datetime import datetime, timezone
from unittest.case import TestCase
from unittest.mock import Mock, call, patch

# third party
from requests.models import HTTPError, Response
from semantic_version import Version

# inception sdk
from inception_sdk.test_framework import endtoend
from inception_sdk.test_framework.endtoend.core_api_helper import (
    create_product_version,
    get_vault_version,
    update_account_schedule_tag,
)
from inception_sdk.test_framework.endtoend.schedule_helper import AccountScheduleTagStatusOverride

HTTP_400_ERROR_MSG = "400 Client Error: Bad Request"
HTTP_500_ERROR_MSG = "500 Internal Server Error: Service Unavailable"
HTTP_503_ERROR_MSG = "503 Server Error: Service Unavailable"


class CoreApiHelperTest(TestCase):
    @patch.object(endtoend.helper, "send_request")
    def test_vault_version(self, mock_send_request: Mock):
        mock_send_request.return_value = {
            "version": {"major": 4, "minor": 3, "patch": 1, "label": "-rc3"}
        }
        vault_version = get_vault_version()
        self.assertEqual(vault_version, Version("4.3.1-rc3"))

    @patch.object(endtoend.helper, "send_request")
    def test_update_account_schedule_tag_expected_result_test_pause_at_timestamp(
        self,
        mock_send_request: Mock,
    ):
        tag_id = "ACCOUNT_SCHEDULE_TAG"
        test_pause_at_timestamp = datetime(2021, 1, 1, tzinfo=timezone.utc).isoformat()
        new_tag_state = {"test_pause_at_timestamp": test_pause_at_timestamp}
        mock_send_request.return_value = new_tag_state
        updated_tag = update_account_schedule_tag(
            account_schedule_tag_id=tag_id,
            test_pause_at_timestamp=test_pause_at_timestamp,
        )
        self.assertEqual(updated_tag, new_tag_state)

    @patch.object(endtoend.helper, "send_request")
    def test_update_account_schedule_tag_status_override_to_skipped(
        self,
        mock_send_request: Mock,
    ):
        tag_id = "ACCOUNT_SCHEDULE_TAG"
        test_pause_at_timestamp = datetime(2021, 1, 1, tzinfo=timezone.utc).isoformat()
        start_timestamp = datetime.min.isoformat()
        end_timestamp = datetime.max.isoformat()
        new_tag_state = {
            "test_pause_at_timestamp": test_pause_at_timestamp,
            "schedule_status_override": AccountScheduleTagStatusOverride.SKIPPED,
            "schedule_status_override_start_timestamp": datetime.min.isoformat(),
            "schedule_status_override_end_timestamp": datetime.max.isoformat(),
        }
        mock_send_request.return_value = new_tag_state
        updated_tag = update_account_schedule_tag(
            account_schedule_tag_id=tag_id,
            test_pause_at_timestamp=test_pause_at_timestamp,
            schedule_status_override_start_timestamp=start_timestamp,
            schedule_status_override_end_timestamp=end_timestamp,
            schedule_status_override=AccountScheduleTagStatusOverride.SKIPPED,
        )
        self.assertEqual(updated_tag, new_tag_state)

    @patch.object(endtoend.helper, "send_request")
    @patch.object(endtoend.helper, "sleep")
    @patch.object(endtoend.helper.log, "exception")
    def test_update_account_schedule_tag_update_never_completes(
        self,
        mock_log_exception: Mock,
        mock_sleep: Mock,
        mock_send_request: Mock,
    ):
        tag_id = "ACCOUNT_SCHEDULE_TAG"
        test_pause_at_timestamp = datetime(2021, 1, 2, tzinfo=timezone.utc).isoformat()
        mock_send_request.return_value = {
            "test_pause_at_timestamp": datetime(2021, 1, 1, tzinfo=timezone.utc).isoformat()
        }
        with self.assertRaises(Exception) as context:
            update_account_schedule_tag(
                account_schedule_tag_id=tag_id,
                test_pause_at_timestamp=test_pause_at_timestamp,
            )
        self.assertEqual(type(context.exception), ValueError)
        self.assertIn(
            "Wrapped result {'test_pause_at_timestamp': '2021-01-01T00:00:00+00:00'} does not match"
            " {'test_pause_at_timestamp': '2021-01-02T00:00:00+00:00'}",
            str(context.exception),
        )
        mock_sleep.assert_has_calls([call(10), call(20), call(40), call(80), call(160)])
        mock_log_exception.assert_called_once()

    @patch.object(endtoend.helper, "send_request")
    @patch.object(endtoend.helper, "sleep")
    def test_update_account_schedule_tag_first_call_http_error(
        self,
        mock_sleep: Mock,
        mock_send_request: Mock,
    ):
        tag_id = "ACCOUNT_SCHEDULE_TAG"
        test_pause_at_timestamp = datetime(2021, 1, 1, tzinfo=timezone.utc).isoformat()
        new_tag_state = {"test_pause_at_timestamp": test_pause_at_timestamp}
        mock_send_request.side_effect = [
            HTTPError(HTTP_400_ERROR_MSG),
            new_tag_state,
        ]
        updated_tag = update_account_schedule_tag(
            account_schedule_tag_id=tag_id,
            test_pause_at_timestamp=test_pause_at_timestamp,
        )
        self.assertEqual(updated_tag, new_tag_state)
        mock_sleep.assert_called_once()

    @patch.object(endtoend.helper, "send_request")
    @patch.object(endtoend.helper, "sleep")
    @patch.object(endtoend.helper.log, "exception")
    def test_update_account_schedule_tag_update_fails_http_error(
        self,
        mock_log_exception: Mock,
        mock_sleep: Mock,
        mock_send_request: Mock,
    ):
        tag_id = "ACCOUNT_SCHEDULE_TAG"
        test_pause_at_timestamp = datetime(2021, 1, 1, tzinfo=timezone.utc).isoformat()
        mock_send_request.side_effect = [
            HTTPError(HTTP_503_ERROR_MSG),
            HTTPError(HTTP_503_ERROR_MSG),
            HTTPError(HTTP_503_ERROR_MSG),
            HTTPError(HTTP_503_ERROR_MSG),
            HTTPError(HTTP_503_ERROR_MSG),
            HTTPError(HTTP_503_ERROR_MSG),
        ]
        with self.assertRaises(Exception) as context:
            update_account_schedule_tag(
                account_schedule_tag_id=tag_id,
                test_pause_at_timestamp=test_pause_at_timestamp,
            )
        self.assertEqual(type(context.exception), HTTPError)
        mock_sleep.assert_has_calls([call(10), call(20), call(40), call(80), call(160)])
        mock_log_exception.assert_called_once()

    @patch.object(endtoend.helper, "send_request")
    def test_create_product_version_retries(self, mock_send_request: Mock):

        url = "/v1/product-versions"
        data = json.dumps(
            {
                "request_id": "dummy_request_id",
                "product_version": {
                    "product_id": "dummy_product_id",
                    "code": "dummy_code",
                    "supported_denominations": ["dummy_denomination"],
                    "params": None,
                    "tags": [],
                    "display_name": "",
                    "description": "",
                    "summary": "",
                },
                "is_internal": False,
                "migration_strategy": "PRODUCT_VERSION_MIGRATION_STRATEGY_UNKNOWN",
            }
        )

        test_cases = [
            {
                "description": "ok response does not retry",
                "exception_type": None,
                "response_msg": "200 Ok",
                # originall call + 0 retries
                "number_of_request_calls": 1,
            },
            {
                "description": "400 HTTP error does not retry",
                "exception_type": HTTPError,
                "response_msg": HTTP_400_ERROR_MSG,
                # originall call + 0 retries
                "number_of_request_calls": 1,
            },
            {
                "description": "500 HTTP error retries 5 times",
                "exception_type": HTTPError,
                "response_msg": HTTP_500_ERROR_MSG,
                # originall call + 5 retries
                "number_of_request_calls": 6,
            },
            {
                "description": "503 HTTP error retries 5 times",
                "exception_type": HTTPError,
                "response_msg": HTTP_503_ERROR_MSG,
                # originall call + 5 retries
                "number_of_request_calls": 6,
            },
            {
                "description": "non HTTP error does not retry",
                "exception_type": ValueError,
                "response_msg": "13 lucky for some",
                # originall call + 0 retries
                "number_of_request_calls": 1,
            },
        ]

        for test_case in test_cases:

            status_code = int(test_case["response_msg"].split()[0])

            if test_case["exception_type"] is not None:
                return_error = mock_send_request.return_value = test_case["exception_type"](
                    test_case["response_msg"]
                )
                response = return_error.response = Response()
                response.status_code = status_code
                mock_send_request.side_effect = return_error

                with self.assertRaises(test_case["exception_type"]) as err:
                    create_product_version(
                        request_id="dummy_request_id",
                        code="dummy_code",
                        product_id="dummy_product_id",
                        supported_denominations=["dummy_denomination"],
                    )
                self.assertEqual(err.exception.response.status_code, status_code)

            else:
                response = mock_send_request.return_value = Response()
                response.status_code = status_code
                response._content = json.dumps({"some_response": "1"})

                result = create_product_version(
                    request_id="dummy_request_id",
                    code="dummy_code",
                    product_id="dummy_product_id",
                    supported_denominations=["dummy_denomination"],
                )
                self.assertEqual(result._content, json.dumps({"some_response": "1"}))

            mock_send_request.assert_has_calls(
                [call("post", url, data=data) for _ in range(test_case["number_of_request_calls"])]
            )
            self.assertEqual(
                mock_send_request.call_count,
                test_case["number_of_request_calls"],
                test_case["description"],
            )
            mock_send_request.reset_mock()
