# standard libs
from typing import Any
from unittest.mock import Mock, sentinel

# third party
from confluent_kafka import Consumer, Message

# inception sdk
from inception_sdk.common.python.file_utils import load_file_contents


class MockMessage(Mock):
    def __init__(
        self,
        error: Any | None = None,
        value: str | bytes | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(name="InceptionKafkaMockMessage", **kwargs, spec=Message)
        if isinstance(value, str):
            value = value.encode(encoding="utf-8")
        self.error = Mock(return_value=error)
        self.value = Mock(return_value=value)


class MockConsumer(Mock):
    def __init__(
        self,
        response_messages: list[MockMessage] | None = None,
        response_message_file: str | None = None,
        **kwargs,
    ):
        if response_message_file:
            messages = iter([MockMessage(value=load_file_contents(response_message_file))])
        elif response_messages:
            messages = iter(response_messages)
        else:
            raise ValueError(
                "One of `response_message_file`, `response_messages` must be specified"
            )

        mock_poll = Mock(side_effect=lambda timeout: next(messages, None))

        mock_consumer = Mock()
        mock_consumer.get_watermark_offsets.return_value = (
            sentinel.low_offset,
            sentinel.high_offset,
        )

        mock_subscribe = Mock(
            side_effect=lambda topic, on_assign: on_assign(mock_consumer, [Mock()])
        )

        super().__init__(
            name="InceptionKafkaMockConsumer",
            poll=mock_poll,
            subscribe=mock_subscribe,
            **kwargs,
            spec=Consumer,
        )
