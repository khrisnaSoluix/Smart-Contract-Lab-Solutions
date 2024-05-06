# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
import logging
import os
from functools import wraps

# inception sdk
import inception_sdk.test_framework.endtoend as endtoend
from inception_sdk.common.kafka import (  # noqa: F401
    acked,
    initialise_consumer,
    initialise_producer,
    produce_message,
    subscribe_to_topics,
    wait_for_messages,
)

log = logging.getLogger(__name__)
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class UnsupportedError(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


def kafka_only_helper(func):
    @wraps(func)
    def wrapper(*arg, **kwargs):
        if not endtoend.testhandle.use_kafka:
            raise UnsupportedError(f"{func.__name__}() requires Kafka to be enabled")
        return func(*arg, **kwargs)

    return wrapper


def kafka_only_test(func):
    @wraps(func)
    def wrapper(self):
        if not endtoend.testhandle.use_kafka:
            self.skipTest("Kafka is required to run this test")
        return func(self)

    return wrapper


def initialise_all_consumers(
    topics: list[str],
    consumer_config: dict[str, str | bool | int] | None = None,
):
    """
    Initialises consumers for required topics
    :param topic: list[str], list of Kafka topics to subsscribe to
    """

    # Consumers are initialised and destroyed at a test class level, so we should
    # only be initialising once for each topic
    endtoend.testhandle.kafka_consumers = subscribe_to_topics(
        topics=topics,
        consumer_config=consumer_config or {},
    )
