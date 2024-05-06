from ...common.tests.test_types import PublicCommonV350TypesTestCase
from ....version_340.supervisor_contracts.tests import test_types
from .....utils.tools import SupervisorContracts350TestCase


class PublicSupervisorContractsV350TypesTestCase(
    SupervisorContracts350TestCase,
    PublicCommonV350TypesTestCase,
    test_types.PublicSupervisorContractsV340TypesTestCase
):
    pass
