from datetime import datetime
import uuid

from ....version_380.common.tests.test_types import PublicCommonV380TypesTestCase


class PublicCommonV390TypesTestCase(PublicCommonV380TypesTestCase):
    TS_380 = datetime(year=2021, month=1, day=1)
    request_id_380 = str(uuid.uuid4())
    account_id_380 = 'test_account_id_380'
