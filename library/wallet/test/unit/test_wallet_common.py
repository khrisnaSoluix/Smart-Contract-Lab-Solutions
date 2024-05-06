# standard libs
from datetime import datetime
from decimal import Decimal
from json import dumps
from unittest.mock import Mock
from zoneinfo import ZoneInfo

# contracts api
from contracts_api import Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ContractTest,
    construct_parameter_timeseries,
)

DEFAULT_DATETIME = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))

DECIMAL_ZERO = Decimal(0)

DEFAULT_DENOMINATION = "SGD"
DEFAULT_CUSTOMER_WALLET_LIMIT = Decimal("1000")
DEFAULT_ACCOUNT_ID = "Main account"
DEFAULT_NOMINATED_ACCOUNT = "Some Account"
DEFAULT_INTERNAL_ACCOUNT = "1"
DEFAULT_DAILY_SPENDING_LIMIT = Decimal("100")
DEFAULT_ADDITIONAL_DENOMINATIONS = dumps(["GBP", "USD"])

DEFAULT_ZERO_OUT_DAILY_SPEND_HOUR = 23
DEFAULT_ZERO_OUT_DAILY_SPEND_MINUTE = 59
DEFAULT_ZERO_OUT_DAILY_SPEND_SECOND = 59

DUPLICATION = "duplication"
TODAYS_SPENDING = "todays_spending"

default_parameters = {
    "zero_out_daily_spend_hour": DEFAULT_ZERO_OUT_DAILY_SPEND_HOUR,
    "zero_out_daily_spend_minute": DEFAULT_ZERO_OUT_DAILY_SPEND_MINUTE,
    "zero_out_daily_spend_second": DEFAULT_ZERO_OUT_DAILY_SPEND_SECOND,
    "denomination": DEFAULT_DENOMINATION,
    "daily_spending_limit": DEFAULT_DAILY_SPENDING_LIMIT,
    "nominated_account": DEFAULT_NOMINATED_ACCOUNT,
    "additional_denominations": DEFAULT_ADDITIONAL_DENOMINATIONS,
    "customer_wallet_limit": DEFAULT_CUSTOMER_WALLET_LIMIT,
}


class WalletTestBase(ContractTest):
    tside = Tside.LIABILITY
    default_denomination = DEFAULT_DENOMINATION

    def create_mock(self, creation_date: datetime = DEFAULT_DATETIME, **kwargs) -> Mock:
        return super().create_mock(
            creation_date=creation_date,
            parameter_ts=construct_parameter_timeseries(
                default_parameters, default_datetime=DEFAULT_DATETIME
            ),
            **kwargs
        )
