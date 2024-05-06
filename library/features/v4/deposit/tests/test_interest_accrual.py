# standard libs
from datetime import datetime
from zoneinfo import ZoneInfo

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest

DEFAULT_DATE = datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))


class InterestAccrualTestCommon(FeatureTest):
    maxDiff = None


class InterestAccrualTest(InterestAccrualTestCommon):
    def test_dummy(self):
        assert True
