# standard libs
from datetime import datetime
from zoneinfo import ZoneInfo

# library
import library.savings_account.contracts.template.savings_account as savings_account

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DENOMINATION,
    ContractTest,
)

DEFAULT_DATE = datetime(2020, 1, 10, tzinfo=ZoneInfo("UTC"))


class SavingsAccountTest(ContractTest):
    contract_file = "library/savings_account/contracts/template/savings_account.py"
    tside = savings_account.tside
    default_denom = DEFAULT_DENOMINATION
