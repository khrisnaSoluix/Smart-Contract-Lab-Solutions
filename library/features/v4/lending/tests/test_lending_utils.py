# standard libs
from decimal import Decimal

# features
from library.features.v4.lending import lending_utils

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest


class IsCreditTest(FeatureTest):
    def test_is_credit(self):
        self.assertTrue(lending_utils.is_credit(amount=Decimal("-1")))

    def test_is_not_credit(self):
        self.assertFalse(lending_utils.is_credit(amount=Decimal("1")))


class IsDebitTest(FeatureTest):
    def test_is_debit(self):
        self.assertTrue(lending_utils.is_debit(amount=Decimal("1")))

    def test_is_not_debit(self):
        self.assertFalse(lending_utils.is_debit(amount=Decimal("-1")))
