# standard libs
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    BalanceDefaultDict,
    Phase,
    Tside,
)

DECIMAL_ZERO = Decimal("0")
CUT_OFF_DATE = datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC"))
CTX_ID_1 = "client_transaction_id_1"
CTX_ID_2 = "client_transaction_id_2"
DEFAULT_ACCOUNT = "default_account"


class CommonTransactionLimitTest(FeatureTest):
    tside = Tside.LIABILITY

    def balances(
        self,
        default_committed: Decimal = DECIMAL_ZERO,
        default_pending_outgoing: Decimal = DECIMAL_ZERO,
        default_pending_incoming: Decimal = DECIMAL_ZERO,
    ) -> BalanceDefaultDict:
        mapping = {
            self.balance_coordinate(): self.balance(net=default_committed),
            self.balance_coordinate(phase=Phase.PENDING_OUT): self.balance(
                net=default_pending_outgoing
            ),
            self.balance_coordinate(phase=Phase.PENDING_IN): self.balance(
                net=default_pending_incoming
            ),
        }
        return BalanceDefaultDict(mapping=mapping)
