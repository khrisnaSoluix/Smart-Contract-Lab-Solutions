# standard libs
import json
from unittest import TestCase
from unittest.mock import ANY, MagicMock, Mock, PropertyMock, patch, sentinel

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.common.python.file_utils import load_file_contents
from inception_sdk.test_framework.endtoend import postings_helper

ERROR_RESPONSE = json.loads(
    load_file_contents(
        "inception_sdk/test_framework/endtoend/test/unit/input/pib_response_errored.json"
    )
)
ACCEPTED_RESPONSE = json.loads(
    load_file_contents(
        "inception_sdk/test_framework/endtoend/test/unit/input/pib_response_accepted.json"
    )
)


@patch.object(postings_helper, "wait_for_posting_responses")
@patch.object(postings_helper, "create_and_produce_posting_request")
@patch.object(endtoend, "testhandle")
class SendAndWaitForPIBTest(TestCase):
    def test_exception_raised_on_error_response(
        self,
        mock_testhandle: Mock,
        mock_create_and_produce_posting_request: Mock,
        mock_wait_for_posting_responses: Mock,
    ):
        error = ERROR_RESPONSE["error"]

        type(mock_testhandle).use_kafka = PropertyMock(return_value=True)
        mock_create_and_produce_posting_request.return_value = "test_request_id"
        mock_wait_for_posting_responses.return_value = ([], {"test_request_id": error})

        with self.assertRaises(ValueError) as ctx:
            postings_helper.send_and_wait_for_posting_instruction_batch(pib=sentinel.input_pib)
        self.assertEqual(
            ctx.exception.args[0],
            f"Posting request_id='test_request_id' resulted in {error=}",
        )

    def test_exception_raised_on_missing_response(
        self,
        mock_testhandle: Mock,
        mock_create_and_produce_posting_request: Mock,
        mock_wait_for_posting_responses: Mock,
    ):

        type(mock_testhandle).use_kafka = PropertyMock(return_value=True)
        mock_create_and_produce_posting_request.return_value = "test_request_id"
        mock_wait_for_posting_responses.return_value = ([], {})

        with self.assertRaises(ValueError) as ctx:
            postings_helper.send_and_wait_for_posting_instruction_batch(pib=sentinel.input_pib)
        self.assertEqual(
            ctx.exception.args[0],
            "No response found for posting request_id='test_request_id'",
        )

    def test_pib_id_returned_on_successful_response(
        self,
        mock_testhandle: Mock,
        mock_create_and_produce_posting_request: Mock,
        mock_wait_for_posting_responses: Mock,
    ):
        expected_pib_id = ACCEPTED_RESPONSE["id"]

        type(mock_testhandle).use_kafka = PropertyMock(return_value=True)
        mock_create_and_produce_posting_request.return_value = "test_request_id"
        mock_wait_for_posting_responses.return_value = ([expected_pib_id], {})

        pib_id = postings_helper.send_and_wait_for_posting_instruction_batch(pib=sentinel.input_pib)
        self.assertEqual(pib_id, expected_pib_id)


class BatchCompletionRecorderTests(TestCase):
    def setUp(self):
        self.recorder = postings_helper.BatchCompletionRecorder()

    def test_batch_completion_recorder_records_successful_response(self):
        self.recorder(ACCEPTED_RESPONSE)
        self.assertListEqual(self.recorder.pib_ids, [ACCEPTED_RESPONSE["id"]])
        self.assertDictEqual(self.recorder.errored_responses, {})

    def test_batch_completion_recorder_records_errored_response(self):
        self.recorder(ERROR_RESPONSE)
        self.assertListEqual(self.recorder.pib_ids, [])
        self.assertDictEqual(
            self.recorder.errored_responses,
            {ERROR_RESPONSE["create_request_id"]: ERROR_RESPONSE["error"]},
        )


@patch.object(postings_helper, "BatchCompletionRecorder")
@patch.object(postings_helper, "wait_for_messages")
@patch.object(endtoend, "testhandle")
class WaitForPostingResponseTest(TestCase):
    def test_wait_for_postings_returns_batch_completion_recorder_results(
        self,
        mock_testhandle: Mock,
        mock_wait_for_messages: Mock,
        mock_BatchCompletionRecorder: MagicMock,
    ):

        mock_batch_completion_recorder = MagicMock(
            spec=postings_helper.BatchCompletionRecorder,
            pib_ids=["a"],
            errored_responses={"b": {"key": "value"}},
        )
        mock_BatchCompletionRecorder.return_value = mock_batch_completion_recorder
        type(mock_testhandle).use_kafka = PropertyMock(return_value=True)
        mock_testhandle.kafka_consumers = {
            postings_helper.POSTINGS_API_RESPONSE_TOPIC: sentinel.postings_consumer
        }

        pib_ids, errored_responses = postings_helper.wait_for_posting_responses(
            request_ids=["a", "b"], migration=False
        )

        mock_wait_for_messages.assert_called_once_with(
            sentinel.postings_consumer,
            matcher=ANY,
            callback=mock_batch_completion_recorder,
            unique_message_ids={"a": None, "b": None},
            inter_message_timeout=30,
            matched_message_timeout=0,
        )

        self.assertListEqual(pib_ids, ["a"])
        self.assertDictEqual(errored_responses, {"b": {"key": "value"}})
