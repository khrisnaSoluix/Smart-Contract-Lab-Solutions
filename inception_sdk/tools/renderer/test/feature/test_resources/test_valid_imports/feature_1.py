# flake8: noqa
# standard libs
from datetime import datetime
from typing import Any

# contracts api
from contracts_api import ScheduleSkip


def get_datetime():
    return datetime.utcnow()
