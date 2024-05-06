# standard libs
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.lending.payments as payments
from library.features.common.fetchers import LIVE_BALANCES_BOF_ID
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import (
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    Posting,
    PostPostingHookArguments,
    SupervisorPostPostingHookArguments,
    Tside,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    CustomInstruction,
    Phase,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelPosting,
)


class PaymentsTestCommon(FeatureTest):
    tside = Tside.ASSET
    maxDiff = None


class CreatePaymentPostingsTest(PaymentsTestCommon):
    common_args = dict(
        debit_account=sentinel.debit_account,
        denomination=sentinel.denomination,
        credit_account=sentinel.credit_account,
        credit_address=sentinel.credit_address,
    )

    def test_redistribute_postings_0_posting_amount(self):
        self.assertEqual(
            [],
            payments.redistribute_postings(amount=Decimal("0"), **self.common_args),
        )

    def test_redistribute_postings_negative_posting_amount(self):
        self.assertEqual(
            [],
            payments.redistribute_postings(amount=Decimal("-1"), **self.common_args),
        )

    def test_redistribute_postings_positive_posting_amount(self):
        self.assertEqual(
            [
                Posting(
                    credit=True,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_id=sentinel.credit_account,
                    account_address=sentinel.credit_address,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_id=sentinel.debit_account,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
            payments.redistribute_postings(amount=Decimal("1"), **self.common_args),
        )

    def test_redistribute_postings_positive_posting_amount_with_debit_address(self):
        debit_address = sentinel.debit_address
        self.assertEqual(
            [
                Posting(
                    credit=True,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_id=sentinel.credit_account,
                    account_address=sentinel.credit_address,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_id=sentinel.debit_account,
                    account_address=debit_address,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
            payments.redistribute_postings(
                amount=Decimal("1"), debit_address=debit_address, **self.common_args
            ),
        )


class DistributeRepaymentsTest(PaymentsTestCommon):
    default_addresses = ["ADDRESS_1", "ADDRESS_2", "ADDRESS_3", "ADDRESS_4"]
    default_balances = BalanceDefaultDict(
        mapping={
            BalanceCoordinate(
                default_addresses[0],
                DEFAULT_ASSET,
                PaymentsTestCommon.default_denomination,
                Phase.COMMITTED,
            ): Balance(net=Decimal("10.00")),
            BalanceCoordinate(
                default_addresses[1],
                DEFAULT_ASSET,
                PaymentsTestCommon.default_denomination,
                Phase.COMMITTED,
            ): Balance(net=Decimal("1.00")),
            BalanceCoordinate(
                default_addresses[2],
                DEFAULT_ASSET,
                PaymentsTestCommon.default_denomination,
                Phase.COMMITTED,
            ): Balance(net=Decimal("0.015")),
            BalanceCoordinate(
                default_addresses[3],
                DEFAULT_ASSET,
                PaymentsTestCommon.default_denomination,
                Phase.COMMITTED,
            ): Balance(net=Decimal("0.10")),
        }
    )

    def test_distribute_repayment_for_single_target_full_repayment(self):
        (
            repayment_per_address,
            overpayment_amount,
        ) = payments.distribute_repayment_for_single_target(
            balances=self.default_balances,
            repayment_amount=Decimal("11.12"),
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_addresses,
        )

        # assertions
        self.assertDictEqual(
            repayment_per_address,
            {
                "ADDRESS_1": payments.RepaymentAmounts(
                    unrounded_amount=Decimal("10.00"), rounded_amount=Decimal("10.00")
                ),
                "ADDRESS_2": payments.RepaymentAmounts(
                    unrounded_amount=Decimal("1.00"), rounded_amount=Decimal("1.00")
                ),
                "ADDRESS_3": payments.RepaymentAmounts(
                    unrounded_amount=Decimal("0.015"), rounded_amount=Decimal("0.02")
                ),
                "ADDRESS_4": payments.RepaymentAmounts(
                    unrounded_amount=Decimal("0.1"), rounded_amount=Decimal("0.1")
                ),
            },
        )
        self.assertEqual(overpayment_amount, Decimal("0.00"))

    def test_distribute_repayment_for_single_target_full_repayment_default_hierarchy(self):
        balances = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    "PRINCIPAL_OVERDUE",
                    DEFAULT_ASSET,
                    PaymentsTestCommon.default_denomination,
                    Phase.COMMITTED,
                ): Balance(net=Decimal("10.00")),
                BalanceCoordinate(
                    "INTEREST_OVERDUE",
                    DEFAULT_ASSET,
                    PaymentsTestCommon.default_denomination,
                    Phase.COMMITTED,
                ): Balance(net=Decimal("1.00")),
                BalanceCoordinate(
                    "PENALTIES",
                    DEFAULT_ASSET,
                    PaymentsTestCommon.default_denomination,
                    Phase.COMMITTED,
                ): Balance(net=Decimal("0.015")),
                BalanceCoordinate(
                    "PRINCIPAL_DUE",
                    DEFAULT_ASSET,
                    PaymentsTestCommon.default_denomination,
                    Phase.COMMITTED,
                ): Balance(net=Decimal("0.10")),
                BalanceCoordinate(
                    "INTEREST_DUE",
                    DEFAULT_ASSET,
                    PaymentsTestCommon.default_denomination,
                    Phase.COMMITTED,
                ): Balance(net=Decimal("0.11")),
            }
        )

        (
            repayment_per_address,
            overpayment_amount,
        ) = payments.distribute_repayment_for_single_target(
            balances=balances,
            repayment_amount=Decimal("11.23"),
            denomination=self.default_denomination,
        )

        # assertions
        self.assertDictEqual(
            repayment_per_address,
            {
                "PRINCIPAL_OVERDUE": (Decimal("10.00"), Decimal("10.00")),
                "INTEREST_OVERDUE": (Decimal("1.00"), Decimal("1.00")),
                "PENALTIES": (Decimal("0.015"), Decimal("0.02")),
                "PRINCIPAL_DUE": (Decimal("0.1"), Decimal("0.1")),
                "INTEREST_DUE": (Decimal("0.11"), Decimal("0.11")),
            },
        )
        self.assertEqual(overpayment_amount, Decimal("0.00"))

    def test_distribute_repayment_for_single_target_partial_repayment(self):
        (
            repayment_per_address,
            overpayment_amount,
        ) = payments.distribute_repayment_for_single_target(
            balances=self.default_balances,
            repayment_amount=Decimal("11.02"),
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_addresses,
        )

        # assertions
        self.assertDictEqual(
            repayment_per_address,
            {
                "ADDRESS_1": (Decimal("10.00"), Decimal("10.00")),
                "ADDRESS_2": (Decimal("1.00"), Decimal("1.00")),
                "ADDRESS_3": (Decimal("0.015"), Decimal("0.02")),
            },
        )
        self.assertEqual(overpayment_amount, Decimal("0.00"))

    def test_distribute_repayment_for_single_target_round_down(self):
        (
            repayment_per_address,
            overpayment_amount,
        ) = payments.distribute_repayment_for_single_target(
            balances=BalanceDefaultDict(
                mapping={
                    BalanceCoordinate(
                        "ADDRESS_1",
                        DEFAULT_ASSET,
                        PaymentsTestCommon.default_denomination,
                        Phase.COMMITTED,
                    ): Balance(net=Decimal("0.012"))
                }
            ),
            repayment_amount=Decimal("0.01"),
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_addresses,
        )

        # assertions
        self.assertDictEqual(
            repayment_per_address,
            {"ADDRESS_1": (Decimal("0.012"), Decimal("0.01"))},
        )
        self.assertEqual(overpayment_amount, Decimal("0.00"))

    def test_distribute_repayment_for_single_target_round_down_underpay(self):
        (
            repayment_per_address,
            overpayment_amount,
        ) = payments.distribute_repayment_for_single_target(
            balances=BalanceDefaultDict(
                mapping={
                    BalanceCoordinate(
                        "ADDRESS_1",
                        DEFAULT_ASSET,
                        PaymentsTestCommon.default_denomination,
                        Phase.COMMITTED,
                    ): Balance(net=Decimal("0.022"))
                }
            ),
            repayment_amount=Decimal("0.01"),
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_addresses,
        )

        # assertions
        self.assertDictEqual(
            repayment_per_address,
            {"ADDRESS_1": (Decimal("0.01"), Decimal("0.01"))},
        )
        self.assertEqual(overpayment_amount, Decimal("0.00"))

    def test_distribute_repayment_for_single_target_round_up(self):
        (
            repayment_per_address,
            overpayment_amount,
        ) = payments.distribute_repayment_for_single_target(
            balances=BalanceDefaultDict(
                mapping={
                    BalanceCoordinate(
                        "ADDRESS_1",
                        DEFAULT_ASSET,
                        PaymentsTestCommon.default_denomination,
                        Phase.COMMITTED,
                    ): Balance(net=Decimal("0.0092"))
                }
            ),
            repayment_amount=Decimal("0.01"),
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_addresses,
        )

        # assertions
        self.assertDictEqual(
            repayment_per_address,
            {"ADDRESS_1": (Decimal("0.0092"), Decimal("0.01"))},
        )
        self.assertEqual(overpayment_amount, Decimal("0.00"))

    def test_distribute_repayment_for_single_target_round_up_underpay(self):
        (
            repayment_per_address,
            overpayment_amount,
        ) = payments.distribute_repayment_for_single_target(
            balances=BalanceDefaultDict(
                mapping={
                    BalanceCoordinate(
                        "ADDRESS_1",
                        DEFAULT_ASSET,
                        PaymentsTestCommon.default_denomination,
                        Phase.COMMITTED,
                    ): Balance(net=Decimal("0.018"))
                }
            ),
            repayment_amount=Decimal("0.01"),
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_addresses,
        )

        # assertions
        self.assertDictEqual(
            repayment_per_address,
            {"ADDRESS_1": (Decimal("0.01"), Decimal("0.01"))},
        )
        self.assertEqual(overpayment_amount, Decimal("0.00"))

    def test_distribute_repayment_for_single_target_round_to_0_overpayment(self):
        (
            repayment_per_address,
            overpayment_amount,
        ) = payments.distribute_repayment_for_single_target(
            balances=BalanceDefaultDict(
                mapping={
                    BalanceCoordinate(
                        "ADDRESS_1",
                        DEFAULT_ASSET,
                        PaymentsTestCommon.default_denomination,
                        Phase.COMMITTED,
                    ): Balance(net=Decimal("0.0042"))
                }
            ),
            repayment_amount=Decimal("0.01"),
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_addresses,
        )

        # assertions
        self.assertDictEqual(
            repayment_per_address,
            {},
        )
        self.assertEqual(overpayment_amount, Decimal("0.01"))

    def test_distribute_repayment_for_single_target_multiple_round_up(self):
        (
            repayment_per_address,
            overpayment_amount,
        ) = payments.distribute_repayment_for_single_target(
            balances=BalanceDefaultDict(
                mapping={
                    BalanceCoordinate(
                        "ADDRESS_1",
                        DEFAULT_ASSET,
                        PaymentsTestCommon.default_denomination,
                        Phase.COMMITTED,
                    ): Balance(net=Decimal("10.00")),
                    # since both of these round to "0.01"
                    # only the first address is fully paid off
                    BalanceCoordinate(
                        "ADDRESS_2",
                        DEFAULT_ASSET,
                        PaymentsTestCommon.default_denomination,
                        Phase.COMMITTED,
                    ): Balance(net=Decimal("0.0052")),
                    BalanceCoordinate(
                        "ADDRESS_3",
                        DEFAULT_ASSET,
                        PaymentsTestCommon.default_denomination,
                        Phase.COMMITTED,
                    ): Balance(net=Decimal("0.0052")),
                }
            ),
            repayment_amount=Decimal("10.01"),
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_addresses,
        )

        # assertions
        self.assertDictEqual(
            repayment_per_address,
            {
                "ADDRESS_1": (Decimal("10.00"), Decimal("10.00")),
                "ADDRESS_2": (Decimal("0.0052"), Decimal("0.01")),
            },
        )
        self.assertEqual(overpayment_amount, Decimal("0.00"))


@patch.object(payments, "distribute_repayment_for_single_target")
class DistributeRepaymentsMultipleTargetsTest(PaymentsTestCommon):
    mock_vault_1 = MagicMock(account_id="loan_1")
    mock_vault_2 = MagicMock(account_id="loan_2")
    default_repayment_hierarchy = [["ADDRESS_1"], ["ADDRESS_2", "ADDRESS_3"]]

    def test_with_single_target(self, mock_distribute_repayment_for_single_target: MagicMock):
        mock_distribute_repayment_for_single_target.side_effect = [
            (
                # Call 1: ["ADDRESS_1"], loan_1
                {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_1_rounded_amount,
                    ),
                },
                sentinel.remaining_repayment_amount,
            ),
            (
                # Call 2: ["ADDRESS_2", "ADDRESS_3"], loan_1
                {
                    "ADDRESS_2": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_2_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_2_loan_1_rounded_amount,
                    ),
                    "ADDRESS_3": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_3_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_3_loan_1_rounded_amount,
                    ),
                },
                sentinel.remaining_repayment_amount,
            ),
        ]

        expected_result = (
            {
                self.mock_vault_1: {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_1_rounded_amount,
                    ),
                    "ADDRESS_2": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_2_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_2_loan_1_rounded_amount,
                    ),
                    "ADDRESS_3": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_3_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_3_loan_1_rounded_amount,
                    ),
                }
            },
            sentinel.remaining_repayment_amount,
        )

        balances_per_target: dict[str, BalanceDefaultDict] = {
            self.mock_vault_1: sentinel.loan_1_balances
        }
        result = payments.distribute_repayment_for_multiple_targets(
            balances_per_target=balances_per_target,
            repayment_amount=sentinel.repayment_amount,
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )

        self.assertEqual(result, expected_result)

        calls = [
            call(
                balances=sentinel.loan_1_balances,
                repayment_amount=sentinel.repayment_amount,
                denomination=self.default_denomination,
                repayment_hierarchy=self.default_repayment_hierarchy[0],
            ),
            call(
                balances=sentinel.loan_1_balances,
                repayment_amount=sentinel.remaining_repayment_amount,
                denomination=self.default_denomination,
                repayment_hierarchy=self.default_repayment_hierarchy[1],
            ),
        ]
        mock_distribute_repayment_for_single_target.assert_has_calls(calls)

    def test_with_one_list_hierarchy(self, mock_distribute_repayment_for_single_target: MagicMock):
        repayment_hierarchy = [["ADDRESS_1", "ADDRESS_2", "ADDRESS_3"]]
        mock_distribute_repayment_for_single_target.side_effect = [
            # Call 1: ["ADDRESS_1", "ADDRESS_2", "ADDRESS_3"], loan_1
            (
                {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_1_rounded_amount,
                    ),
                    "ADDRESS_2": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_2_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_2_loan_1_rounded_amount,
                    ),
                    "ADDRESS_3": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_3_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_3_loan_1_rounded_amount,
                    ),
                },
                sentinel.remaining_repayment_amount,
            ),
            # Call 2: ["ADDRESS_1", "ADDRESS_2", "ADDRESS_3"], loan_2
            (
                {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_2_rounded_amount,
                    ),
                    "ADDRESS_2": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_2_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_2_loan_2_rounded_amount,
                    ),
                    "ADDRESS_3": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_3_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_3_loan_2_rounded_amount,
                    ),
                },
                sentinel.remaining_repayment_amount,
            ),
        ]

        balances_per_target: dict[str, BalanceDefaultDict] = {
            self.mock_vault_1: sentinel.loan_1_balances,
            self.mock_vault_2: sentinel.loan_2_balances,
        }
        result = payments.distribute_repayment_for_multiple_targets(
            balances_per_target=balances_per_target,
            repayment_amount=sentinel.repayment_amount,
            denomination=self.default_denomination,
            repayment_hierarchy=repayment_hierarchy,
        )

        expected_result = (
            {
                self.mock_vault_1: {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_1_rounded_amount,
                    ),
                    "ADDRESS_2": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_2_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_2_loan_1_rounded_amount,
                    ),
                    "ADDRESS_3": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_3_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_3_loan_1_rounded_amount,
                    ),
                },
                self.mock_vault_2: {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_2_rounded_amount,
                    ),
                    "ADDRESS_2": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_2_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_2_loan_2_rounded_amount,
                    ),
                    "ADDRESS_3": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_3_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_3_loan_2_rounded_amount,
                    ),
                },
            },
            sentinel.remaining_repayment_amount,
        )

        self.assertEqual(result, expected_result)

        calls = [
            call(
                balances=sentinel.loan_1_balances,
                repayment_amount=sentinel.repayment_amount,
                denomination=self.default_denomination,
                repayment_hierarchy=repayment_hierarchy[0],
            ),
            call(
                balances=sentinel.loan_2_balances,
                repayment_amount=sentinel.remaining_repayment_amount,
                denomination=self.default_denomination,
                repayment_hierarchy=repayment_hierarchy[0],
            ),
        ]
        mock_distribute_repayment_for_single_target.assert_has_calls(calls)

    def test_full_repayment(self, mock_distribute_repayment_for_single_target: MagicMock):
        mock_distribute_repayment_for_single_target.side_effect = [
            # Call 1: ["ADDRESS_1"], loan_1
            (
                {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_1_rounded_amount,
                    )
                },
                sentinel.remaining_repayment_amount,
            ),
            # Call 2: ["ADDRESS_1"], loan_2
            (
                {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_2_rounded_amount,
                    )
                },
                sentinel.remaining_repayment_amount,
            ),
            # Call 3: ["ADDRESS_2", "ADDRESS_3]", loan_1
            (
                {
                    "ADDRESS_2": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_2_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_2_loan_1_rounded_amount,
                    ),
                    "ADDRESS_3": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_3_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_3_loan_1_rounded_amount,
                    ),
                },
                sentinel.remaining_repayment_amount,
            ),
            # Call 4: ["ADDRESS_2", "ADDRESS_3]", loan_2
            (
                {
                    "ADDRESS_2": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_2_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_2_loan_2_rounded_amount,
                    ),
                    "ADDRESS_3": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_3_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_3_loan_2_rounded_amount,
                    ),
                },
                sentinel.remaining_repayment_amount,
            ),
        ]

        expected_result = (
            {
                self.mock_vault_1: {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_1_rounded_amount,
                    ),
                    "ADDRESS_2": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_2_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_2_loan_1_rounded_amount,
                    ),
                    "ADDRESS_3": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_3_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_3_loan_1_rounded_amount,
                    ),
                },
                self.mock_vault_2: {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_2_rounded_amount,
                    ),
                    "ADDRESS_2": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_2_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_2_loan_2_rounded_amount,
                    ),
                    "ADDRESS_3": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_3_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_3_loan_2_rounded_amount,
                    ),
                },
            },
            sentinel.remaining_repayment_amount,
        )

        balances_per_target: dict[str, BalanceDefaultDict] = {
            self.mock_vault_1: sentinel.loan_1_balances,
            self.mock_vault_2: sentinel.loan_2_balances,
        }
        result = payments.distribute_repayment_for_multiple_targets(
            balances_per_target=balances_per_target,
            repayment_amount=sentinel.repayment_amount,
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )

        self.assertEqual(result, expected_result)

        calls = [
            call(
                balances=sentinel.loan_1_balances,
                repayment_amount=sentinel.repayment_amount,
                denomination=self.default_denomination,
                repayment_hierarchy=self.default_repayment_hierarchy[0],
            ),
            call(
                balances=sentinel.loan_2_balances,
                repayment_amount=sentinel.remaining_repayment_amount,
                denomination=self.default_denomination,
                repayment_hierarchy=self.default_repayment_hierarchy[0],
            ),
            call(
                balances=sentinel.loan_1_balances,
                repayment_amount=sentinel.remaining_repayment_amount,
                denomination=self.default_denomination,
                repayment_hierarchy=self.default_repayment_hierarchy[1],
            ),
            call(
                balances=sentinel.loan_2_balances,
                repayment_amount=sentinel.remaining_repayment_amount,
                denomination=self.default_denomination,
                repayment_hierarchy=self.default_repayment_hierarchy[1],
            ),
        ]
        mock_distribute_repayment_for_single_target.assert_has_calls(calls)

    def test_partial_repayment(self, mock_distribute_repayment_for_single_target: MagicMock):
        mock_distribute_repayment_for_single_target.side_effect = [
            # Call 1: ["ADDRESS_1"], loan_1
            (
                {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_1_rounded_amount,
                    )
                },
                sentinel.remaining_repayment_amount,
            ),
            # Call 2: ["ADDRESS_1"], loan_2
            (
                {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_2_rounded_amount,
                    )
                },
                sentinel.remaining_repayment_amount,
            ),
            # Call 3: ["ADDRESS_2", "ADDRESS_3]", loan_1
            (
                {
                    "ADDRESS_2": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_2_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_2_loan_1_rounded_amount,
                    ),
                },
                Decimal("0"),
            ),
        ]

        expected_result = (
            {
                self.mock_vault_1: {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_1_rounded_amount,
                    ),
                    "ADDRESS_2": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_2_loan_1_unrounded_amount,
                        rounded_amount=sentinel.address_2_loan_1_rounded_amount,
                    ),
                },
                self.mock_vault_2: {
                    "ADDRESS_1": payments.RepaymentAmounts(
                        unrounded_amount=sentinel.address_1_loan_2_unrounded_amount,
                        rounded_amount=sentinel.address_1_loan_2_rounded_amount,
                    ),
                },
            },
            Decimal("0"),
        )

        balances_per_target: dict[str, BalanceDefaultDict] = {
            self.mock_vault_1: sentinel.loan_1_balances,
            self.mock_vault_2: sentinel.loan_2_balances,
        }
        result = payments.distribute_repayment_for_multiple_targets(
            balances_per_target=balances_per_target,
            repayment_amount=sentinel.repayment_amount,
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )

        self.assertEqual(result, expected_result)

        calls = [
            call(
                balances=sentinel.loan_1_balances,
                repayment_amount=sentinel.repayment_amount,
                denomination=self.default_denomination,
                repayment_hierarchy=self.default_repayment_hierarchy[0],
            ),
            call(
                balances=sentinel.loan_2_balances,
                repayment_amount=sentinel.remaining_repayment_amount,
                denomination=self.default_denomination,
                repayment_hierarchy=self.default_repayment_hierarchy[0],
            ),
            call(
                balances=sentinel.loan_1_balances,
                repayment_amount=sentinel.remaining_repayment_amount,
                denomination=self.default_denomination,
                repayment_hierarchy=self.default_repayment_hierarchy[1],
            ),
        ]
        mock_distribute_repayment_for_single_target.assert_has_calls(calls)


@patch.object(payments.early_repayment, "is_posting_an_early_repayment")
@patch.object(payments, "distribute_repayment_for_single_target")
@patch.object(payments.utils, "get_parameter")
@patch.object(payments, "redistribute_postings")
class GenerateRepaymentPostingsTest(PaymentsTestCommon):
    default_account_id = "account-id"
    default_balance_obs = SentinelBalancesObservation("dummy_observation")
    default_date = datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC"))
    default_repayment_amount = Decimal(10.50)
    default_postings = [
        PaymentsTestCommon().inbound_hard_settlement(amount=Decimal(default_repayment_amount))
    ]
    default_repayment_hierarchy = ["PRINCIPAL_DUE", "INTEREST_DUE"]

    def test_do_not_generate_postings_with_repayment_that_rounds_to_0(
        self,
        mock_redistribute_postings: MagicMock,
        mock_get_parameter: MagicMock,
        mock_distribute_repayment_for_single_target: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={LIVE_BALANCES_BOF_ID: self.default_balance_obs},
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": self.default_denomination}
        )
        mock_distribute_repayment_for_single_target.return_value = (
            {
                "ADDRESS_2": (Decimal("0.0043"), Decimal("0.00")),
            },
            Decimal("0.00"),
        )
        mock_redistribute_postings.return_value = self.default_postings
        mock_is_posting_an_early_repayment.return_value = False

        hook_args = PostPostingHookArguments(
            effective_datetime=self.default_date,
            posting_instructions=self.default_postings,
            client_transactions={},
        )
        no_repayment_posting_instructions = payments.generate_repayment_postings(
            vault=mock_vault,
            hook_arguments=hook_args,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )

        # assertions
        mock_distribute_repayment_for_single_target.assert_called_once_with(
            balances=sentinel.balances_dummy_observation,
            repayment_amount=abs(self.default_repayment_amount),
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )
        mock_redistribute_postings.assert_not_called()
        self.assertEqual(no_repayment_posting_instructions, [])

    def test_do_not_generate_postings_with_repayment_that_rounds_to_0_defaulted_hierarchy(
        self,
        mock_redistribute_postings: MagicMock,
        mock_get_parameter: MagicMock,
        mock_distribute_repayment_for_single_target: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={LIVE_BALANCES_BOF_ID: self.default_balance_obs},
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": self.default_denomination}
        )
        mock_distribute_repayment_for_single_target.return_value = (
            {
                "ADDRESS_2": (Decimal("0.0043"), Decimal("0.00")),
            },
            Decimal("0.00"),
        )
        mock_redistribute_postings.return_value = self.default_postings
        mock_is_posting_an_early_repayment.return_value = False

        hook_args = PostPostingHookArguments(
            effective_datetime=self.default_date,
            posting_instructions=self.default_postings,
            client_transactions={},
        )
        no_repayment_posting_instructions = payments.generate_repayment_postings(
            vault=mock_vault,
            hook_arguments=hook_args,
        )

        # assertions
        mock_distribute_repayment_for_single_target.assert_called_once_with(
            balances=sentinel.balances_dummy_observation,
            repayment_amount=abs(self.default_repayment_amount),
            denomination=self.default_denomination,
            repayment_hierarchy=payments.lending_addresses.REPAYMENT_HIERARCHY,
        )
        mock_redistribute_postings.assert_not_called()
        self.assertEqual(no_repayment_posting_instructions, [])

    def test_generate_repayment_postings_with_no_overpayment(
        self,
        mock_redistribute_postings: MagicMock,
        mock_get_parameter: MagicMock,
        mock_distribute_repayment_for_single_target: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            account_id=self.default_account_id,
            balances_observation_fetchers_mapping={LIVE_BALANCES_BOF_ID: self.default_balance_obs},
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": self.default_denomination}
        )
        mock_distribute_repayment_for_single_target.return_value = (
            {
                "ADDRESS_1": (Decimal("10.00"), Decimal("10.00")),
                "ADDRESS_2": (Decimal("0.0043"), Decimal("0.00")),
                "ADDRESS_3": (Decimal("0.015"), Decimal("0.02")),
            },
            Decimal("0.00"),
        )
        mock_repayment_posting = SentinelPosting("dummy_posting")
        mock_redistribute_postings.return_value = [mock_repayment_posting]
        mock_is_posting_an_early_repayment.return_value = False

        hook_args = PostPostingHookArguments(
            effective_datetime=self.default_date,
            posting_instructions=self.default_postings,
            client_transactions={},
        )
        repayment_posting_instructions = payments.generate_repayment_postings(
            vault=mock_vault,
            hook_arguments=hook_args,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )

        # assertions
        mock_distribute_repayment_for_single_target.assert_called_once_with(
            balances=sentinel.balances_dummy_observation,
            repayment_amount=abs(self.default_repayment_amount),
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )
        mock_redistribute_postings.assert_has_calls(
            [
                call(
                    debit_account=self.default_account_id,
                    amount=Decimal("10.00"),
                    denomination=self.default_denomination,
                    credit_account=self.default_account_id,
                    credit_address="ADDRESS_1",
                ),
                call(
                    debit_account=self.default_account_id,
                    amount=Decimal("0.02"),
                    denomination=self.default_denomination,
                    credit_account=self.default_account_id,
                    credit_address="ADDRESS_3",
                ),
            ]
        )
        expected_posting_instructions = [
            CustomInstruction(
                # These represent the two postings that should be made
                # that correspond to ADDRESS_1 and ADDRESS_3 above
                postings=[mock_repayment_posting] * 2,
                instruction_details={
                    "description": "Process a repayment",
                    "event": "PROCESS_REPAYMENTS",
                },
            )
        ]
        self.assertEqual(repayment_posting_instructions, expected_posting_instructions)

    def test_generate_repayment_postings_with_overpayment_but_no_overpayment_feature(
        self,
        mock_redistribute_postings: MagicMock,
        mock_get_parameter: MagicMock,
        mock_distribute_repayment_for_single_target: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={LIVE_BALANCES_BOF_ID: self.default_balance_obs},
        )
        mock_distribute_repayment_for_single_target.return_value = (
            {},
            Decimal("0.02"),
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": self.default_denomination}
        )
        mock_is_posting_an_early_repayment.return_value = False

        hook_args = PostPostingHookArguments(
            effective_datetime=self.default_date,
            posting_instructions=self.default_postings,
            client_transactions={},
        )
        no_repayment_or_overpayment_posting_instructions = payments.generate_repayment_postings(
            vault=mock_vault,
            hook_arguments=hook_args,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )

        # assertions
        mock_distribute_repayment_for_single_target.assert_called_once_with(
            balances=sentinel.balances_dummy_observation,
            repayment_amount=self.default_repayment_amount,
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )
        mock_redistribute_postings.assert_not_called()
        self.assertEqual(no_repayment_or_overpayment_posting_instructions, [])

    def test_generate_repayment_postings_with_overpayment_and_overpayment_feature(
        self,
        mock_redistribute_postings: MagicMock,
        mock_get_parameter: MagicMock,
        mock_distribute_repayment_for_single_target: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={LIVE_BALANCES_BOF_ID: self.default_balance_obs},
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": self.default_denomination}
        )
        overpayment_posting = SentinelPosting("dummy_posting")
        mock_distribute_repayment_for_single_target.return_value = (
            {},
            Decimal("0.02"),
        )
        mock_overpayment_feature = MagicMock(
            handle_overpayment=MagicMock(return_value=[overpayment_posting]),
        )
        mock_is_posting_an_early_repayment.return_value = False

        hook_args = PostPostingHookArguments(
            effective_datetime=self.default_date,
            posting_instructions=self.default_postings,
            client_transactions={},
        )
        overpayment_posting_instruction = payments.generate_repayment_postings(
            vault=mock_vault,
            hook_arguments=hook_args,
            repayment_hierarchy=self.default_repayment_hierarchy,
            overpayment_features=[mock_overpayment_feature],
        )

        # assertions
        mock_distribute_repayment_for_single_target.assert_called_once_with(
            balances=sentinel.balances_dummy_observation,
            repayment_amount=self.default_repayment_amount,
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )
        mock_redistribute_postings.assert_not_called()
        expected_posting_instructions = [
            CustomInstruction(
                postings=[overpayment_posting],
                instruction_details={
                    "description": "Process repayment overpayment",
                    "event": "PROCESS_REPAYMENTS",
                },
            )
        ]
        self.assertEqual(overpayment_posting_instruction, expected_posting_instructions)

    def test_generate_repayment_postings_with_repayment_and_overpayment_postings(
        self,
        mock_redistribute_postings: MagicMock,
        mock_get_parameter: MagicMock,
        mock_distribute_repayment_for_single_target: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            account_id=self.default_account_id,
            balances_observation_fetchers_mapping={LIVE_BALANCES_BOF_ID: self.default_balance_obs},
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": self.default_denomination}
        )
        mock_repayment_posting = SentinelPosting("dummy_repayment_posting")
        mock_overpayment_posting = SentinelPosting("dummy_overpayment_posting")
        mock_distribute_repayment_for_single_target.return_value = (
            {
                "ADDRESS_1": (Decimal("10.00"), Decimal("10.00")),
                "ADDRESS_2": (Decimal("0.0043"), Decimal("0.00")),
                "ADDRESS_3": (Decimal("0.015"), Decimal("0.02")),
            },
            Decimal("0.02"),
        )
        mock_redistribute_postings.return_value = [mock_repayment_posting]
        mock_overpayment_feature = MagicMock(
            handle_overpayment=MagicMock(return_value=[mock_overpayment_posting]),
        )
        mock_is_posting_an_early_repayment.return_value = False

        hook_args = PostPostingHookArguments(
            effective_datetime=self.default_date,
            posting_instructions=self.default_postings,
            client_transactions={},
        )
        repayment_and_overpayment_posting_instructions = payments.generate_repayment_postings(
            vault=mock_vault,
            hook_arguments=hook_args,
            repayment_hierarchy=self.default_repayment_hierarchy,
            overpayment_features=[mock_overpayment_feature],
        )

        # assertions
        mock_distribute_repayment_for_single_target.assert_called_once_with(
            balances=sentinel.balances_dummy_observation,
            repayment_amount=self.default_repayment_amount,
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )
        mock_redistribute_postings.assert_has_calls(
            [
                call(
                    debit_account=self.default_account_id,
                    amount=Decimal("10.00"),
                    denomination=self.default_denomination,
                    credit_account=self.default_account_id,
                    credit_address="ADDRESS_1",
                ),
                call(
                    debit_account=self.default_account_id,
                    amount=Decimal("0.02"),
                    denomination=self.default_denomination,
                    credit_account=self.default_account_id,
                    credit_address="ADDRESS_3",
                ),
            ]
        )
        expected_posting_instructions = [
            CustomInstruction(
                postings=[mock_repayment_posting, mock_repayment_posting],
                instruction_details={
                    "description": "Process a repayment",
                    "event": "PROCESS_REPAYMENTS",
                },
            ),
            CustomInstruction(
                postings=[mock_overpayment_posting],
                instruction_details={
                    "description": "Process repayment overpayment",
                    "event": "PROCESS_REPAYMENTS",
                },
            ),
        ]
        self.assertEqual(
            repayment_and_overpayment_posting_instructions, expected_posting_instructions
        )

    def test_generate_repayment_postings_with_multiple_overpayment_features(
        self,
        mock_redistribute_postings: MagicMock,
        mock_get_parameter: MagicMock,
        mock_distribute_repayment_for_single_target: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            account_id=self.default_account_id,
            balances_observation_fetchers_mapping={LIVE_BALANCES_BOF_ID: self.default_balance_obs},
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": self.default_denomination}
        )
        mock_repayment_posting = SentinelPosting("dummy_repayment_posting")
        mock_overpayment_posting_1 = SentinelPosting("dummy_overpayment_posting_1")
        mock_overpayment_posting_2 = SentinelPosting("dummy_overpayment_posting_2")
        mock_distribute_repayment_for_single_target.return_value = (
            {
                "ADDRESS_1": (Decimal("10.00"), Decimal("10.00")),
                "ADDRESS_2": (Decimal("0.0043"), Decimal("0.00")),
                "ADDRESS_3": (Decimal("0.015"), Decimal("0.02")),
            },
            Decimal("0.02"),
        )
        mock_redistribute_postings.return_value = [mock_repayment_posting]
        mock_overpayment_feature_1 = MagicMock(
            handle_overpayment=MagicMock(return_value=[mock_overpayment_posting_1]),
        )
        mock_overpayment_feature_2 = MagicMock(
            handle_overpayment=MagicMock(return_value=[mock_overpayment_posting_2]),
        )
        mock_is_posting_an_early_repayment.return_value = False

        hook_args = PostPostingHookArguments(
            effective_datetime=self.default_date,
            posting_instructions=self.default_postings,
            client_transactions={},
        )
        repayment_and_overpayment_posting_instructions = payments.generate_repayment_postings(
            vault=mock_vault,
            hook_arguments=hook_args,
            repayment_hierarchy=self.default_repayment_hierarchy,
            overpayment_features=[mock_overpayment_feature_1, mock_overpayment_feature_2],
        )

        # assertions
        mock_distribute_repayment_for_single_target.assert_called_once_with(
            balances=sentinel.balances_dummy_observation,
            repayment_amount=self.default_repayment_amount,
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )
        mock_redistribute_postings.assert_has_calls(
            [
                call(
                    debit_account=self.default_account_id,
                    amount=Decimal("10.00"),
                    denomination=self.default_denomination,
                    credit_account=self.default_account_id,
                    credit_address="ADDRESS_1",
                ),
                call(
                    debit_account=self.default_account_id,
                    amount=Decimal("0.02"),
                    denomination=self.default_denomination,
                    credit_account=self.default_account_id,
                    credit_address="ADDRESS_3",
                ),
            ]
        )
        expected_posting_instructions = [
            CustomInstruction(
                postings=[mock_repayment_posting, mock_repayment_posting],
                instruction_details={
                    "description": "Process a repayment",
                    "event": "PROCESS_REPAYMENTS",
                },
            ),
            CustomInstruction(
                postings=[mock_overpayment_posting_1],
                instruction_details={
                    "description": "Process repayment overpayment",
                    "event": "PROCESS_REPAYMENTS",
                },
            ),
            CustomInstruction(
                postings=[mock_overpayment_posting_2],
                instruction_details={
                    "description": "Process repayment overpayment",
                    "event": "PROCESS_REPAYMENTS",
                },
            ),
        ]
        self.assertEqual(
            repayment_and_overpayment_posting_instructions, expected_posting_instructions
        )

    @patch.object(
        payments.interest_capitalisation, "handle_overpayments_to_penalties_pending_capitalisation"
    )
    def test_generate_repayment_postings_with_early_repayment_and_early_repayment_fees(
        self,
        mock_handle_overpayments_to_penalties_pending_capitalisation: MagicMock,
        mock_redistribute_postings: MagicMock,
        mock_get_parameter: MagicMock,
        mock_distribute_repayment_for_single_target: MagicMock,
        mock_is_posting_an_early_repayment: MagicMock,
    ):
        # setup mocks
        mock_vault = self.create_mock(
            account_id=self.default_account_id,
            balances_observation_fetchers_mapping={LIVE_BALANCES_BOF_ID: self.default_balance_obs},
        )
        mock_handle_overpayments_to_penalties_pending_capitalisation.return_value = [
            sentinel.instruction_for_penalties_pending_capitalisation
        ]
        mock_distribute_repayment_for_single_target.return_value = (
            {},
            Decimal("0.02"),
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"denomination": self.default_denomination}
        )
        mock_is_posting_an_early_repayment.return_value = True

        charge_early_repayment_fee_mock_1 = MagicMock(
            return_value=[sentinel.fee_posting_instruction_1]
        )
        charge_early_repayment_fee_mock_2 = MagicMock(
            return_value=[sentinel.fee_posting_instruction_2]
        )

        mock_early_repayment_fee_1 = MagicMock(
            charge_early_repayment_fee=charge_early_repayment_fee_mock_1,
            get_early_repayment_fee_amount=MagicMock(return_value=Decimal("10")),
            fee_name=sentinel.fee_name,
        )
        mock_early_repayment_fee_2 = MagicMock(
            charge_early_repayment_fee=charge_early_repayment_fee_mock_2,
            get_early_repayment_fee_amount=MagicMock(return_value=Decimal("500")),
            fee_name=sentinel.fee_name,
        )

        hook_args = PostPostingHookArguments(
            effective_datetime=self.default_date,
            posting_instructions=self.default_postings,
            client_transactions={},
        )
        returned_posting_instructions = payments.generate_repayment_postings(
            vault=mock_vault,
            hook_arguments=hook_args,
            repayment_hierarchy=self.default_repayment_hierarchy,
            early_repayment_fees=[mock_early_repayment_fee_1, mock_early_repayment_fee_2],
        )

        # assertions
        mock_distribute_repayment_for_single_target.assert_called_once_with(
            balances=sentinel.balances_dummy_observation,
            repayment_amount=self.default_repayment_amount,
            denomination=self.default_denomination,
            repayment_hierarchy=self.default_repayment_hierarchy,
        )
        self.assertListEqual(
            [
                sentinel.instruction_for_penalties_pending_capitalisation,
                sentinel.fee_posting_instruction_1,
                sentinel.fee_posting_instruction_2,
            ],
            returned_posting_instructions,
        )
        charge_early_repayment_fee_mock_1.assert_called_once_with(
            vault=mock_vault,
            account_id=self.default_account_id,
            amount_to_charge=Decimal("10"),
            fee_name=sentinel.fee_name,
            denomination=self.default_denomination,
        )
        charge_early_repayment_fee_mock_2.assert_called_once_with(
            vault=mock_vault,
            account_id=self.default_account_id,
            amount_to_charge=Decimal("500"),
            fee_name=sentinel.fee_name,
            denomination=self.default_denomination,
        )


class GenerateRepaymentPostingsForMultipleTargets(PaymentsTestCommon):
    main_vault = sentinel.main_vault
    main_vault.account_id = "main_vault"

    loan_1_vault = sentinel.loan_1_vault
    loan_1_vault.account_id = "loan_1_vault"

    loan_2_vault = sentinel.loan_2_vault
    loan_2_vault.account_id = "loan_2_vault"

    ADDRESS_1 = "ADDRESS_1"
    ADDRESS_2 = "ADDRESS_2"
    ADDRESS_3 = "ADDRESS_3"
    repayment_hierarchy = [[ADDRESS_1], [ADDRESS_2], [ADDRESS_3]]

    def setUp(self) -> None:
        self.mock_get_denomination_parameter = patch.object(
            payments.common_parameters, "get_denomination_parameter"
        ).start()
        self.mock_balance_at_coordinates = patch.object(
            payments.utils, "balance_at_coordinates"
        ).start()
        self.mock_get_balances_default_dicts_from_timeseries = patch.object(
            payments.supervisor_utils, "get_balances_default_dicts_from_timeseries"
        ).start()
        self.mock_distribute_repayment_for_multiple_targets = patch.object(
            payments, "distribute_repayment_for_multiple_targets"
        ).start()
        self.mock_redistribute_postings = patch.object(payments, "redistribute_postings").start()

        self.mock_get_denomination_parameter.return_value = self.default_denomination
        self.mock_balance_at_coordinates.return_value = Decimal("-100")

        self.balances_per_target = {
            self.main_vault.account_id: sentinel.main_vault_balances,
            self.loan_1_vault.account_id: sentinel.loan_1_balances,
            self.loan_2_vault.account_id: sentinel.loan_2_balances,
        }
        self.mock_get_balances_default_dicts_from_timeseries.return_value = self.balances_per_target
        self.main_vault_repayment_dict = {
            self.ADDRESS_1: payments.RepaymentAmounts(
                unrounded_amount=sentinel.main_address_1_unrounded_amount,
                rounded_amount=sentinel.main_address_1_rounded_amount,
            ),
            self.ADDRESS_2: payments.RepaymentAmounts(
                unrounded_amount=sentinel.main_address_2_unrounded_amount,
                rounded_amount=sentinel.main_address_2_rounded_amount,
            ),
        }
        self.loan_1_vault_repayment_dict = {
            self.ADDRESS_1: payments.RepaymentAmounts(
                unrounded_amount=sentinel.loan_1_address_1_unrounded_amount,
                rounded_amount=sentinel.loan_1_address_1_rounded_amount,
            ),
            self.ADDRESS_2: payments.RepaymentAmounts(
                unrounded_amount=sentinel.loan_1_address_2_unrounded_amount,
                rounded_amount=sentinel.loan_1_address_2_rounded_amount,
            ),
        }
        self.loan_2_vault_repayment_dict = {
            self.ADDRESS_1: payments.RepaymentAmounts(
                unrounded_amount=sentinel.loan_2_address_1_unrounded_amount,
                rounded_amount=sentinel.loan_2_address_1_rounded_amount,
            ),
            self.ADDRESS_2: payments.RepaymentAmounts(
                unrounded_amount=Decimal("0"),
                rounded_amount=Decimal("0"),
            ),
        }
        self.repayments_per_target = {
            self.main_vault.account_id: self.main_vault_repayment_dict,
            self.loan_1_vault.account_id: self.loan_1_vault_repayment_dict,
            self.loan_2_vault.account_id: self.loan_2_vault_repayment_dict,
        }
        self.mock_distribute_repayment_for_multiple_targets.return_value = (
            self.repayments_per_target,
            Decimal("50"),
        )
        self.mock_redistribute_postings.side_effect = [
            [SentinelPosting("main_vault_address_1_posting")],
            [SentinelPosting("main_vault_address_2_posting")],
            [SentinelPosting("loan_1_address_1_posting")],
            [SentinelPosting("loan_1_address_2_posting")],
            [SentinelPosting("loan_2_address_1_posting")],
            [SentinelPosting("loan_2_address_2_posting")],
        ]
        self.redistribute_postings_calls = [
            call(
                debit_account=self.main_vault.account_id,
                amount=sentinel.main_address_1_rounded_amount,
                denomination=self.default_denomination,
                credit_account=self.main_vault.account_id,
                credit_address=self.ADDRESS_1,
                debit_address=DEFAULT_ADDRESS,
            ),
            call(
                debit_account=self.main_vault.account_id,
                amount=sentinel.main_address_2_rounded_amount,
                denomination=self.default_denomination,
                credit_account=self.main_vault.account_id,
                credit_address=self.ADDRESS_2,
                debit_address=DEFAULT_ADDRESS,
            ),
            call(
                debit_account=self.loan_1_vault.account_id,
                amount=sentinel.loan_1_address_1_rounded_amount,
                denomination=self.default_denomination,
                credit_account=self.loan_1_vault.account_id,
                credit_address=self.ADDRESS_1,
                debit_address=payments.lending_addresses.INTERNAL_CONTRA,
            ),
            call(
                debit_account=self.loan_1_vault.account_id,
                amount=sentinel.loan_1_address_2_rounded_amount,
                denomination=self.default_denomination,
                credit_account=self.loan_1_vault.account_id,
                credit_address=self.ADDRESS_2,
                debit_address=payments.lending_addresses.INTERNAL_CONTRA,
            ),
            call(
                debit_account=self.loan_2_vault.account_id,
                amount=sentinel.loan_2_address_1_rounded_amount,
                denomination=self.default_denomination,
                credit_account=self.loan_2_vault.account_id,
                credit_address=self.ADDRESS_1,
                debit_address=payments.lending_addresses.INTERNAL_CONTRA,
            ),
        ]

        self.main_vault_posting_instructions = [
            CustomInstruction(
                postings=[
                    SentinelPosting("main_vault_address_1_posting"),
                    SentinelPosting("main_vault_address_2_posting"),
                ],
                instruction_details={
                    "description": "Process a repayment",
                    "event": "PROCESS_REPAYMENTS",
                },
            )
        ]
        self.loan_1_vault_posting_instructions = [
            CustomInstruction(
                postings=[
                    SentinelPosting("loan_1_address_1_posting"),
                    SentinelPosting("loan_1_address_2_posting"),
                ],
                instruction_details={
                    "description": "Process a repayment",
                    "event": "PROCESS_REPAYMENTS",
                },
            )
        ]
        self.loan_2_vault_posting_instructions = [
            CustomInstruction(
                postings=[
                    SentinelPosting("loan_2_address_1_posting"),
                ],
                instruction_details={
                    "description": "Process a repayment",
                    "event": "PROCESS_REPAYMENTS",
                },
            )
        ]

        self.overpayment_feature_1 = MagicMock()
        self.overpayment_feature_1.handle_overpayment.return_value = {
            self.loan_1_vault.account_id: [SentinelPosting("overpayment_feature_1_loan_1")],
            self.loan_2_vault.account_id: [SentinelPosting("overpayment_feature_1_loan_2")],
        }
        self.overpayment_feature_2 = MagicMock()
        self.overpayment_feature_2.handle_overpayment.return_value = {
            self.loan_1_vault.account_id: [SentinelPosting("overpayment_feature_2_loan_1")],
            self.loan_2_vault.account_id: [SentinelPosting("overpayment_feature_2_loan_2")],
        }
        self.overpayment_features: list[payments.lending_interfaces.MultiTargetOverpayment] = [
            self.overpayment_feature_1,
            self.overpayment_feature_2,
        ]

        self.loan_1_overpayment_instructions = [
            CustomInstruction(
                postings=[
                    SentinelPosting("overpayment_feature_1_loan_1"),
                    SentinelPosting("overpayment_feature_2_loan_1"),
                ],
                instruction_details={
                    "description": "Process repayment overpayment",
                    "event": "PROCESS_REPAYMENTS",
                },
            )
        ]
        self.loan_2_overpayment_instructions = [
            CustomInstruction(
                postings=[
                    SentinelPosting("overpayment_feature_1_loan_2"),
                    SentinelPosting("overpayment_feature_2_loan_2"),
                ],
                instruction_details={
                    "description": "Process repayment overpayment",
                    "event": "PROCESS_REPAYMENTS",
                },
            )
        ]

        self.supervisee_posting_instructions = {
            self.main_vault.account_id: [self.inbound_hard_settlement(amount=Decimal("100"))]
        }
        self.hook_arguments = SupervisorPostPostingHookArguments(
            effective_datetime=DEFAULT_DATETIME,
            supervisee_posting_instructions=self.supervisee_posting_instructions,
            supervisee_client_transactions={},
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_no_repayment_postings(self):
        self.mock_balance_at_coordinates.return_value = Decimal("0")

        expected_result = {
            self.main_vault.account_id: [],
            self.loan_1_vault.account_id: [],
            self.loan_2_vault.account_id: [],
        }

        result = payments.generate_repayment_postings_for_multiple_targets(
            main_vault=self.main_vault,
            sorted_repayment_targets=[self.main_vault, self.loan_1_vault, self.loan_2_vault],
            hook_arguments=self.hook_arguments,
            repayment_hierarchy=self.repayment_hierarchy,
            overpayment_features=self.overpayment_features,
        )

        self.assertEqual(result, expected_result)

        self.mock_get_denomination_parameter.assert_called_once_with(vault=self.main_vault)
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=self.supervisee_posting_instructions[self.main_vault.account_id][0].balances(),
            denomination=self.default_denomination,
        )
        self.mock_get_balances_default_dicts_from_timeseries.assert_not_called()
        self.mock_distribute_repayment_for_multiple_targets.assert_not_called()
        self.mock_redistribute_postings.assert_not_called()
        for overpayment_feature in self.overpayment_features:
            overpayment_feature.handle_overpayment.assert_not_called()

    def test_repayment_amount_is_greater_than_0(self):
        self.mock_balance_at_coordinates.return_value = Decimal("100")

        expected_result = {
            self.main_vault.account_id: [],
            self.loan_1_vault.account_id: [],
            self.loan_2_vault.account_id: [],
        }

        result = payments.generate_repayment_postings_for_multiple_targets(
            main_vault=self.main_vault,
            sorted_repayment_targets=[self.main_vault, self.loan_1_vault, self.loan_2_vault],
            hook_arguments=self.hook_arguments,
            repayment_hierarchy=self.repayment_hierarchy,
            overpayment_features=self.overpayment_features,
        )

        self.assertEqual(result, expected_result)

        self.mock_get_denomination_parameter.assert_called_once_with(vault=self.main_vault)
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=self.supervisee_posting_instructions[self.main_vault.account_id][0].balances(),
            denomination=self.default_denomination,
        )
        self.mock_get_balances_default_dicts_from_timeseries.assert_not_called()
        self.mock_distribute_repayment_for_multiple_targets.assert_not_called()
        self.mock_redistribute_postings.assert_not_called()
        for overpayment_feature in self.overpayment_features:
            overpayment_feature.handle_overpayment.assert_not_called()

    def test_with_no_overpayment(self):
        self.mock_distribute_repayment_for_multiple_targets.return_value = (
            self.repayments_per_target,
            Decimal("0"),
        )

        expected_result = {
            self.main_vault.account_id: self.main_vault_posting_instructions,
            self.loan_1_vault.account_id: self.loan_1_vault_posting_instructions,
            self.loan_2_vault.account_id: self.loan_2_vault_posting_instructions,
        }

        result = payments.generate_repayment_postings_for_multiple_targets(
            main_vault=self.main_vault,
            sorted_repayment_targets=[self.main_vault, self.loan_1_vault, self.loan_2_vault],
            hook_arguments=self.hook_arguments,
            repayment_hierarchy=self.repayment_hierarchy,
            overpayment_features=self.overpayment_features,
        )

        self.assertEqual(result, expected_result)

        self.mock_get_denomination_parameter.assert_called_once_with(vault=self.main_vault)
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=self.supervisee_posting_instructions[self.main_vault.account_id][0].balances(),
            denomination=self.default_denomination,
        )
        self.mock_get_balances_default_dicts_from_timeseries.assert_called_once_with(
            supervisees=[self.main_vault, self.loan_1_vault, self.loan_2_vault],
            effective_datetime=self.hook_arguments.effective_datetime,
        )
        self.mock_distribute_repayment_for_multiple_targets.assert_called_once_with(
            balances_per_target=self.balances_per_target,
            repayment_amount=Decimal("100"),
            denomination=self.default_denomination,
            repayment_hierarchy=self.repayment_hierarchy,
        )
        self.mock_redistribute_postings.assert_has_calls(self.redistribute_postings_calls)
        for overpayment_feature in self.overpayment_features:
            overpayment_feature.handle_overpayment.assert_not_called()

    def test_with_overpayment_but_no_overpayment_features(self):
        expected_result = {
            self.main_vault.account_id: self.main_vault_posting_instructions,
            self.loan_1_vault.account_id: self.loan_1_vault_posting_instructions,
            self.loan_2_vault.account_id: self.loan_2_vault_posting_instructions,
        }

        result = payments.generate_repayment_postings_for_multiple_targets(
            main_vault=self.main_vault,
            sorted_repayment_targets=[self.main_vault, self.loan_1_vault, self.loan_2_vault],
            hook_arguments=self.hook_arguments,
            repayment_hierarchy=self.repayment_hierarchy,
        )

        self.assertEqual(result, expected_result)

        self.mock_get_denomination_parameter.assert_called_once_with(vault=self.main_vault)
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=self.supervisee_posting_instructions[self.main_vault.account_id][0].balances(),
            denomination=self.default_denomination,
        )
        self.mock_get_balances_default_dicts_from_timeseries.assert_called_once_with(
            supervisees=[self.main_vault, self.loan_1_vault, self.loan_2_vault],
            effective_datetime=self.hook_arguments.effective_datetime,
        )
        self.mock_distribute_repayment_for_multiple_targets.assert_called_once_with(
            balances_per_target=self.balances_per_target,
            repayment_amount=Decimal("100"),
            denomination=self.default_denomination,
            repayment_hierarchy=self.repayment_hierarchy,
        )
        self.mock_redistribute_postings.assert_has_calls(self.redistribute_postings_calls)

    def test_with_overpayment_and_overpayment_features(self):
        expected_result = {
            self.main_vault.account_id: self.main_vault_posting_instructions,
            self.loan_1_vault.account_id: self.loan_1_vault_posting_instructions
            + self.loan_1_overpayment_instructions,
            self.loan_2_vault.account_id: self.loan_2_vault_posting_instructions
            + self.loan_2_overpayment_instructions,
        }

        result = payments.generate_repayment_postings_for_multiple_targets(
            main_vault=self.main_vault,
            sorted_repayment_targets=[self.main_vault, self.loan_1_vault, self.loan_2_vault],
            hook_arguments=self.hook_arguments,
            repayment_hierarchy=self.repayment_hierarchy,
            overpayment_features=self.overpayment_features,
        )

        self.assertEqual(result, expected_result)

        self.mock_get_denomination_parameter.assert_called_once_with(vault=self.main_vault)
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=self.supervisee_posting_instructions[self.main_vault.account_id][0].balances(),
            denomination=self.default_denomination,
        )
        self.mock_get_balances_default_dicts_from_timeseries.assert_called_once_with(
            supervisees=[self.main_vault, self.loan_1_vault, self.loan_2_vault],
            effective_datetime=self.hook_arguments.effective_datetime,
        )
        self.mock_distribute_repayment_for_multiple_targets.assert_called_once_with(
            balances_per_target=self.balances_per_target,
            repayment_amount=Decimal("100"),
            denomination=self.default_denomination,
            repayment_hierarchy=self.repayment_hierarchy,
        )
        self.mock_redistribute_postings.assert_has_calls(self.redistribute_postings_calls)
        for overpayment_feature in self.overpayment_features:
            overpayment_feature.handle_overpayment.assert_called_once_with(
                main_vault=self.main_vault,
                overpayment_amount=Decimal("50"),
                balances_per_target_vault={
                    target: self.balances_per_target[target.account_id]
                    for target in [self.main_vault, self.loan_1_vault, self.loan_2_vault]
                },
                denomination=self.default_denomination,
            )

    def test_no_hierarchy_provided(self):
        expected_result = {
            self.main_vault.account_id: self.main_vault_posting_instructions,
            self.loan_1_vault.account_id: self.loan_1_vault_posting_instructions
            + self.loan_1_overpayment_instructions,
            self.loan_2_vault.account_id: self.loan_2_vault_posting_instructions
            + self.loan_2_overpayment_instructions,
        }

        result = payments.generate_repayment_postings_for_multiple_targets(
            main_vault=self.main_vault,
            sorted_repayment_targets=[self.main_vault, self.loan_1_vault, self.loan_2_vault],
            hook_arguments=self.hook_arguments,
            overpayment_features=self.overpayment_features,
        )

        self.assertEqual(
            result[self.loan_1_vault.account_id], expected_result[self.loan_1_vault.account_id]
        )

        self.mock_get_denomination_parameter.assert_called_once_with(vault=self.main_vault)
        self.mock_balance_at_coordinates.assert_called_once_with(
            balances=self.supervisee_posting_instructions[self.main_vault.account_id][0].balances(),
            denomination=self.default_denomination,
        )
        self.mock_get_balances_default_dicts_from_timeseries.assert_called_once_with(
            supervisees=[self.main_vault, self.loan_1_vault, self.loan_2_vault],
            effective_datetime=self.hook_arguments.effective_datetime,
        )
        self.mock_distribute_repayment_for_multiple_targets.assert_called_once_with(
            balances_per_target=self.balances_per_target,
            repayment_amount=Decimal("100"),
            denomination=self.default_denomination,
            repayment_hierarchy=[
                [address] for address in payments.lending_addresses.REPAYMENT_HIERARCHY
            ],
        )
        self.mock_redistribute_postings.assert_has_calls(self.redistribute_postings_calls)
        for overpayment_feature in self.overpayment_features:
            overpayment_feature.handle_overpayment.assert_called_once_with(
                main_vault=self.main_vault,
                overpayment_amount=Decimal("50"),
                balances_per_target_vault={
                    target: self.balances_per_target[target.account_id]
                    for target in [self.main_vault, self.loan_1_vault, self.loan_2_vault]
                },
                denomination=self.default_denomination,
            )
