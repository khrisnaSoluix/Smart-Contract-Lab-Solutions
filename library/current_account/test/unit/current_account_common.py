# standard libs
from datetime import datetime
from zoneinfo import ZoneInfo

# library
import library.current_account.contracts.template.current_account as current_account

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DENOMINATION,
    ContractTest,
)

DEFAULT_DATE = datetime(2020, 1, 10, tzinfo=ZoneInfo("UTC"))


class CurrentAccountTest(ContractTest):
    contract_file = "library/current_account/contracts/template/current_account.py"
    tside = current_account.tside
    default_denom = DEFAULT_DENOMINATION
