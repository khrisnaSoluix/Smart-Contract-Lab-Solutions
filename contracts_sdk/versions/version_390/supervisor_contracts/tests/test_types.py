from datetime import datetime

from ...common.tests.test_types import PublicCommonV390TypesTestCase
from ....version_380.supervisor_contracts.tests import test_types
from .....utils.tools import SupervisorContracts390TestCase


class PublicSupervisorContractsV390TypesTestCase(
    SupervisorContracts390TestCase,
    PublicCommonV390TypesTestCase,
    test_types.PublicSupervisorContractsV380TypesTestCase
):
    TS_390 = datetime(year=2020, month=1, day=1)
    plan_id_390 = 'test_plan_id'
