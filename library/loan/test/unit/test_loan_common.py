# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from zoneinfo import ZoneInfo

# library
from library.loan.test import parameters

# contracts api
from contracts_api import Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import ContractTest

DEFAULT_DATETIME = datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC"))


class LoanTestBase(ContractTest):
    tside = Tside.ASSET
    default_denomination = parameters.TEST_DENOMINATION
