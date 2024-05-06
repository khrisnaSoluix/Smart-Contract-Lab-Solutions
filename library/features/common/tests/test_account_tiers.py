# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard libs
from json import dumps, loads

# common
from inception_sdk.test_framework.contracts.unit.common import (
    ContractFeatureTest,
)
from library.features.common.account_tiers import get_account_tier

ACCOUNT_TIER_NAMES = dumps(
    [
        "TIER_UPPER",
        "TIER_MIDDLE",
        "TIER_LOWER",
    ]
)


class AccountTiersTest(ContractFeatureTest):
    target_test_file = "library/features/common/account_tiers.py"

    def test_get_account_tier_returns_flag_value(self):
        test_tier = "TIER_MIDDLE"
        mock_vault = self.create_mock(account_tier_names=ACCOUNT_TIER_NAMES, flags=[test_tier])

        account_tier = get_account_tier(mock_vault)

        self.assertEqual(account_tier, test_tier)

    def test_get_account_tier_returns_last_tier_if_no_flag(self):
        mock_vault = self.create_mock(
            account_tier_names=ACCOUNT_TIER_NAMES,
        )

        account_tier = get_account_tier(mock_vault)

        self.assertEqual(account_tier, loads(ACCOUNT_TIER_NAMES)[-1])

    def test_get_account_tier_returns_first_in_tier_name_param_if_multiple_flags_exist(self):
        test_flags = ["TIER_LOWER", "TIER_UPPER"]
        mock_vault = self.create_mock(account_tier_names=ACCOUNT_TIER_NAMES, flags=test_flags)

        account_tier = get_account_tier(mock_vault)

        # returns the first entry in ACCOUNT_TIER_NAMES param that matches a flag
        self.assertEqual(account_tier, "TIER_UPPER")
