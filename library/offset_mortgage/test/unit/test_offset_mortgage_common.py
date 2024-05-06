# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# contracts api
from contracts_api import Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.supervisor.common import (
    SupervisorContractTest,
)

DEFAULT_DENOMINATION = "GBP"


class OffsetMortgageTestBase(SupervisorContractTest):
    tside = Tside.ASSET
    default_denomination = DEFAULT_DENOMINATION
