from ..types import BalancesFilter
from ...common.tests.test_types import PublicCommonV3100TypesTestCase
from ....version_390.smart_contracts.tests import test_types

from .....utils.exceptions import InvalidSmartContractError, StrongTypingError
from .....utils.tools import SmartContracts3100TestCase


class PublicSmartContractsV3100TypesTestCase(
    SmartContracts3100TestCase,
    PublicCommonV3100TypesTestCase,
    test_types.PublicSmartContractsV390TypesTestCase,
):
    def test_balances_filter(self):
        addresses = ["CUSTOM_ADDRESS", "DEFAULT_ADDRESS"]
        balances_filter = BalancesFilter(addresses=addresses)
        self.assertEqual(addresses, balances_filter.addresses)

    def test_balances_filter_with_empty_addresses(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesFilter(addresses=[])
        self.assertEqual(
            str(e.exception), "BalancesFilter addresses must contain at least one address."
        )

    def test_balances_filter_with_empty_address_field(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesFilter()
        self.assertEqual(
            str(e.exception),
            "BalancesFilter.__init__ arg 'addresses' expected List[str] but got value None",
        )

    def test_balances_filter_with_duplicate_addresses(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesFilter(addresses=["address_1", "address_1"])
        self.assertEqual(
            str(e.exception), "BalancesFilter addresses must not contain any duplicate addresses."
        )

    def test_balances_filter_invalid_argument_type(self):
        with self.assertRaises(StrongTypingError):
            BalancesFilter(addresses=[123])
