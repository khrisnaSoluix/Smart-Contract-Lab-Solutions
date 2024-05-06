# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from datetime import datetime
from zoneinfo import ZoneInfo

# library
import library.us_products.contracts.template.us_checking_account as us_checking_account
from library.us_products.test import parameters

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import ContractTest

DEFAULT_DATE = datetime(2020, 1, 10, tzinfo=ZoneInfo("UTC"))


class CheckingAccountTest(ContractTest):
    tside = us_checking_account.tside
    default_denomination = parameters.TEST_DENOMINATION
