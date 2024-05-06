from ...common.tests.test_types import PublicCommonV360TypesTestCase
from ....version_350.supervisor_contracts.tests import test_types
from .....utils.tools import SupervisorContracts360TestCase


class PublicSupervisorContractsV360TypesTestCase(
    SupervisorContracts360TestCase,
    PublicCommonV360TypesTestCase,
    test_types.PublicSupervisorContractsV350TypesTestCase
):
    pass
