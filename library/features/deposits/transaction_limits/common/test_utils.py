# standard library
from datetime import datetime
from decimal import Decimal
from typing import Union

# inception imports
from inception_sdk.test_framework.contracts.unit.common import ContractFeatureTest
from inception_sdk.vault.contracts.types_extension import BalanceDefaultDict, Tside


class TransactionLimitFeatureTest(ContractFeatureTest):
    EOD_DATETIME = datetime(2022, 1, 1, 23, 59, 59)
    side = Tside.LIABILITY

    def default_balances(self, amount: Union[Decimal, str, int]) -> BalanceDefaultDict:
        balance_ts: list[tuple[datetime, BalanceDefaultDict]] = self.init_balances(
            balance_defs=[{"net": str(amount)}]
        )
        _, balances = balance_ts[-1]
        return balances
