# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import json
import logging
import os
import queue
import time
import uuid
from typing import Any, Callable

# third party
from confluent_kafka import Consumer, KafkaError, KafkaException, Producer

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

DEFAULT_PRODUCER_CONFIG: dict[str, bool | int | str] = {}


def error_cb(kafka_error: KafkaError):
    # In a prod service we would check .fatal() too, but for the purposes of the SDK
    # we are fairly aggressive so we can exit tests early and avoid confusing outcomes
    # / unnecessary delays
    if not kafka_error.retriable():
        log.error(f"Unexpected unretriable Kafka error {kafka_error.str()}")
        raise KafkaException(kafka_error)
    else:
        log.warning(f"Unexpected retriable kafka error {kafka_error.str()}")


DEFAULT_CONSUMER_CONFIG: dict[str, bool | int | str | Callable] = {
    "enable.auto.commit": True,
    "api.version.request": True,
    # Optimise the consumers for low latency.  If we find we
    # need super-high throughput we can introduce a separate
    # factory function for that.
    "fetch.wait.max.ms": 100,
    "log.connection.close": False,
    # Max number of bytes per partition returned by the server
    "max.partition.fetch.bytes": 1024 * 1024 * 5,
    "statistics.interval.ms": 15000,
    # This is per partition. The default buffers 1GB which can easily
    # jump over the container mem limits if the consumer starts lagging
    # behind
    "queued.max.messages.kbytes": 1024 * 32,
    "socket.keepalive.enable": True,
    # 15 minutes is about the maximum duration of one of the inception
    # tests, and so this is roughly the amount of time a consumer would
    # go without polling
    # Note 15 * 60 * 1000 = 900000
    "max.poll.interval.ms": "900000",
    # Under heavy load the heartbeats sometimes go missing and consumers get removed from the group
    # Higher timeout makes this much less likely without many side-effects as we only have one
    # consumer per group anyway
    "session.timeout.ms": "100000",
    # Uncomment this to enable debug logging
    # "debug": "all",
    "error_cb": error_cb,
}


class UnsupportedError(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


def initialise_consumer(
    config: dict[str, bool | int | str] | None = None,
) -> Consumer:
    """
    Initialises a kafka consumer relying on default config that can be overridden
    :param config: if specified, the default config is updated with the contents of this dictionary
     This means it takes precedence over any default config or other parameters
    :return: the initialised kafka consumer
    """

    final_config = DEFAULT_CONSUMER_CONFIG.copy()
    final_config.update(config or {})
    if not final_config.get("group.id"):
        final_config["group.id"] = f"e2e_{str(uuid.uuid4())}"
    return Consumer(final_config)


def initialise_producer(
    config: dict[str, bool | int | str] | None = None,
) -> Producer:
    """
    Initialises a kafka producer relying on default config that can be overridden
    :param kafka_config: the kafka config to use. If the KafkaConfig.config is specified,
     the default config is updated with the contents of this dictionary. This means it takes
     precedence over any default config or other parameters
    :param client_id: the client id that the producer will use
    :return: the initialised kafka producer
    """

    final_config = DEFAULT_PRODUCER_CONFIG.copy()
    if config:
        final_config.update(config)

    return Producer(final_config)


def wait_for_messages(
    consumer: Consumer,
    matcher: Callable,
    callback: Callable | None,
    unique_message_ids: dict[str, Any],
    inter_message_timeout: int = 30,
    matched_message_timeout: int = 30,
) -> dict[str, Any]:
    """
    Using the consumer, poll the topic for any matched messages.
    :param consumer: a Kafka topic consumer
    :param matcher: a callable used to determine if any messages received by the consumer are valid
    messages. This method must return a tuple (str, str, bool). The first str is the resulting
    matched event_id, the second str is the matched message unique request id and is used for
    idempotency and the bool is whether the message is matched or not.
    :param callback: called when a message has been matched
    :param unique_message_ids: dict of unique message ids passed to the matcher,
    e.g. dict of account ids. The value can be used to hold any additional information to
    be manipulated in either the matcher or callback functions, otherwise a dummy value (None)
    should be provided.
    :param inter_message_timeout: a maximum time to wait between receiving any messages from the
    consumer (0 for no timeout)
    :param matched_message_timeout: a maximum time to wait between receiving matched messages from
    the consumer (0 for no timeout)
    :return: dict of message ids that failed to match. This is the exact same data structure
    as message_ids
    """
    last_message_time = time.time()
    last_matched_message_time = time.time()
    seen_matched_message_requests: set[str] = set()

    while len(unique_message_ids) > 0:
        msg = consumer.poll(0.1)
        if matched_message_timeout:
            delay = time.time() - last_matched_message_time
            if delay > matched_message_timeout:
                log.warning(
                    f"Waited {delay:.1f}s since last matched message received. "
                    f"Timeout set to {matched_message_timeout:.1f}. Exiting "
                    f"after {len(seen_matched_message_requests)} "
                    f"messages received"
                )
                break
        if msg is None:
            if inter_message_timeout:
                delay = time.time() - last_message_time
                if delay > inter_message_timeout:
                    log.warning(
                        f"Waited {delay:.1f}s since last message received. "
                        f"Timeout set to {inter_message_timeout:.1f}. Exiting "
                        f"after {len(seen_matched_message_requests)} "
                        f"messages received"
                    )
                    break
        else:
            last_message_time = time.time()
            if not msg.error():
                event_msg = json.loads(msg.value().decode())
                (
                    event_id,
                    event_request_id,
                    is_matched,
                ) = matcher(event_msg, unique_message_ids)
                if is_matched and event_request_id not in seen_matched_message_requests:
                    last_matched_message_time = time.time()
                    seen_matched_message_requests.add(event_request_id)

                    if event_id:
                        del unique_message_ids[event_id]
                    if callback:
                        callback(event_msg)
            elif msg.error().code() == KafkaError._PARTITION_EOF:
                log.error("End of partition reached {0}/{1}".format(msg.topic(), msg.partition()))
            else:
                log.error("Error occurred: {0}".format(msg.error().str()))

    return unique_message_ids


def acked(err, msg):
    if err is not None:
        log.exception(f"Failed to deliver message: {msg.value()}: {err.str()}")
    else:
        log.debug("Message produced: {0}".format(msg.value()))


def produce_message(
    producer: Producer,
    topic: str,
    message: str,
    key: str | None = None,
    on_delivery: Callable = acked,
):
    producer.produce(topic=topic, key=key, value=message, on_delivery=on_delivery)
    producer.poll(0)


def subscribe_to_topics(
    topics: list[str],
    consumer_config: dict[str, str | bool | int] | None = None,
) -> dict[str, Consumer]:
    """
    Initialises consumers for required topics, waiting for queue assignment before returning
    :param topic: list of Kafka topics to subscribe to
    :param consumer_config: Consumer config to override any defaults
    :return: dict of topic to initialised consumer
    """

    consumers: dict[str, Consumer] = {}
    assign_queue: queue.Queue = queue.Queue()

    def assign_cb(consumer, partitions):
        # Instead of subscribing, getting the offset assignments, and then
        # changing the offset assignments in this assign_cb callback function,
        # as we are doing now, it might be possible to get away with just calling
        # consumer.assign() in the topic loop below because, with the current setup,
        # there will only ever be 1 consumer per consumer group, and so the partitions
        # that are assigned can be inferred beforehand. However, the pattern implemented
        # here seems to be more in line with best practices and is also more resilient to change.
        # See this thread for more info:
        # https://github.com/confluentinc/confluent-kafka-python/issues/373#issuecomment-389095624
        for partition in partitions:
            partition.offset = consumer.get_watermark_offsets(partition)[1]

        consumer.assign(partitions)
        assign_queue.get()
        assign_queue.task_done()

    log.info(f"Subscribing to {len(topics)} consumers...")
    for topic in topics:
        log.info(f"Subscribing to topic: {topic}...")
        consumers[topic] = initialise_consumer(config=consumer_config)
        assign_queue.put(topic, block=False)
        consumers[topic].subscribe([topic], on_assign=assign_cb)

    # Wait until all new consumers have been assigned partitions. As we use latest
    # auto.offset.reset, messages produced before consumer readiness could otherwise be missed
    while not assign_queue.empty():
        for consumer in consumers.values():
            consumer.poll(0.1)

    log.info("Finished waiting for the assign callbacks, returning the consumers.")
    return consumers
