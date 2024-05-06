# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.

# inception sdk
from inception_sdk.test_framework.endtoend.test.unit.input import dummy_feature

display_name = "Contract for event type replacement tests"
api = "4.0.0"
version = "1.0.0"
summary = "Contract for event type replacement tests"

event_types = dummy_feature.get_event_types("DUMMY")
