# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import ContractTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import Tside


class BNPLTest(ContractTest):
    tside = Tside.ASSET
    default_repayment_count = 4
    default_repayment_frequency = "monthly"
