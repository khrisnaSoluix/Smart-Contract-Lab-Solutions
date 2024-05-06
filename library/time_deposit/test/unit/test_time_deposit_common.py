# library
import library.time_deposit.contracts.template.time_deposit as time_deposit

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DENOMINATION,
    ContractTest,
)


class TimeDepositTest(ContractTest):
    tside = time_deposit.tside
    default_denom = DEFAULT_DENOMINATION
