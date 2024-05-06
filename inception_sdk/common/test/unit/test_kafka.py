# standard libs
from datetime import datetime
from unittest import TestCase
from unittest.mock import Mock, patch

# third party
import freezegun
from confluent_kafka import KafkaException

# inception sdk
import inception_sdk.common.kafka as kafka
from inception_sdk.common.test.mocks.kafka import MockConsumer

SAMPLE_BALANCE_MESSAGE = "inception_sdk/common/test/unit/input/sample_balance_update_event.json"


class KafkaErrorCbTest(TestCase):
    def test_error_cb_raises_on_non_retriable(self):
        mock_error = Mock(retriable=Mock(return_value=False))
        with self.assertRaises(KafkaException):
            kafka.error_cb(kafka_error=mock_error)

    def test_error_cb_does_not_raise_on_retriable(self):
        mock_error = Mock(retriable=Mock(return_value=True))
        self.assertIsNone(kafka.error_cb(kafka_error=mock_error))


class KafkaTest(TestCase):
    def test_wait_for_messages_partial_match(self):
        def matcher(event_msg, unique_message_ids):
            account_id = event_msg["account_id"]
            request_id = event_msg["event_id"]
            return (
                account_id,
                request_id,
                True if account_id in unique_message_ids else ("", request_id, False),
            )

        message_ids = {"1": None, "2": None, "3": None}

        consumer = MockConsumer(response_message_file=SAMPLE_BALANCE_MESSAGE)

        result = kafka.wait_for_messages(
            consumer=consumer,
            matcher=matcher,
            callback=None,
            unique_message_ids=message_ids,
            matched_message_timeout=0,
            inter_message_timeout=-1,
        )

        expected_result = {"2": None, "3": None}
        self.assertEqual(result, expected_result)

    @freezegun.freeze_time(datetime(2020, 1, 1, 1, 1, 1), auto_tick_seconds=1)
    @patch("logging.Logger.warning")
    def test_wait_for_messages_matched_message_timeout(self, warning_logging: Mock):
        def matcher(event_msg, unique_message_ids):
            account_id = event_msg["account_id"]
            request_id = event_msg["event_id"]
            return (
                account_id,
                request_id,
                True if account_id in unique_message_ids else ("", request_id, False),
            )

        message_ids = {"1": None, "2": None, "3": None}

        consumer = MockConsumer(response_message_file=SAMPLE_BALANCE_MESSAGE)

        # freeze_time will increment time by 1s each time we call time.time()in this method,
        # allowing us to trigger retry logic etc
        result = kafka.wait_for_messages(
            consumer=consumer,
            matcher=matcher,
            callback=None,
            unique_message_ids=message_ids,
            matched_message_timeout=1,
            inter_message_timeout=0,
        )
        warning_logging.assert_called_with(
            "Waited 2.0s since last matched message received. "
            "Timeout set to 1.0. Exiting after 1 "
            "messages received"
        )
        expected_result = {"2": None, "3": None}
        self.assertEqual(result, expected_result)

    @freezegun.freeze_time(datetime(2020, 1, 1, 1, 1, 1), auto_tick_seconds=1)
    @patch("logging.Logger.warning")
    def test_wait_for_messages_inter_message_timeout(self, warning_logging: Mock):
        def matcher(event_msg, unique_message_ids):
            account_id = event_msg["account_id"]
            request_id = event_msg["event_id"]
            return (
                account_id,
                request_id,
                True if account_id in unique_message_ids else ("", request_id, False),
            )

        message_ids = {"1": None, "2": None, "3": None}

        consumer = MockConsumer(response_message_file=SAMPLE_BALANCE_MESSAGE)

        # freeze_time will increment time by 1s each time we call time.time() in this method,
        # allowing us to trigger retry logic etc
        result = kafka.wait_for_messages(
            consumer=consumer,
            matcher=matcher,
            callback=None,
            unique_message_ids=message_ids,
            matched_message_timeout=0,
            inter_message_timeout=1,
        )

        warning_logging.assert_called_with(
            "Waited 2.0s since last message received. "
            "Timeout set to 1.0. Exiting after 1 "
            "messages received"
        )
        expected_result = {"2": None, "3": None}
        self.assertEqual(result, expected_result)

    @patch.object(kafka, "Consumer")
    def test_initialise_consumer_overrides_config_from_argument(self, mock_consumer: Mock):
        mock_consumer_instance = Mock()
        mock_consumer_instance.return_value = mock_consumer

        kafka.initialise_consumer(config={"group.id": "1"})

        mock_consumer.assert_called_with({"group.id": "1"} | kafka.DEFAULT_CONSUMER_CONFIG)

    @patch("uuid.uuid4")
    @patch.object(kafka, "Consumer")
    def test_initialise_consumer_creates_a_random_group_id_if_none_is_provided(
        self, mock_consumer: Mock, mock_uuid: Mock
    ):
        mock_consumer_instance = Mock()
        mock_consumer_instance.return_value = mock_consumer
        mock_uuid.return_value = 42

        kafka.initialise_consumer()

        mock_consumer.assert_called_with({"group.id": "e2e_42"} | kafka.DEFAULT_CONSUMER_CONFIG)

    @patch.object(kafka, "initialise_consumer")
    def test_subscribe_to_topics_returns_correct_topic_to_consumer_mapping(
        self, mock_initialise_consumer: Mock
    ):
        consumer1 = MockConsumer(response_message_file=SAMPLE_BALANCE_MESSAGE)
        consumer2 = MockConsumer(response_message_file=SAMPLE_BALANCE_MESSAGE)
        mock_initialise_consumer.side_effect = [consumer1, consumer2]

        result = kafka.subscribe_to_topics(["topic.1", "topic.2"])

        self.assertEqual(result, {"topic.1": consumer1, "topic.2": consumer2})
