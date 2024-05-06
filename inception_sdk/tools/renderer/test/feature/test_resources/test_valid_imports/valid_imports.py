# flake8: noqa
# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
import math
from datetime import datetime
from dateutil.relativedelta import relativedelta

# contracts api
from contracts_api import (
    BalancesFilter,
    PrePostingHookArguments,
    PrePostingHookResult,
    ScheduleSkip,
    Tside,
)

# inception sdk
import inception_sdk.tools.renderer.test.feature.test_resources.test_valid_imports.feature_1 as feature_1  # noqa: E501

api = "4.0.0"
version = "0.0.1"
display_name = "Dummy v4 Contract"
tside = Tside.LIABILITY
supported_denominations = ["GBP", "SGD", "USD"]


def pre_posting_hook(vault, hook_arguments: PrePostingHookArguments) -> PrePostingHookResult | None:
    get_datetime(BalancesFilter())


def get_datetime(param: BalancesFilter | ScheduleSkip):
    current_time = datetime.utcnow()
    another_time = feature_1.get_datetime() + relativedelta(minutes=math.ceil(0))

    return current_time > another_time
