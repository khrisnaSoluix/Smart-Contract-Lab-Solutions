# standard library
from decimal import Decimal

# common
from inception_sdk.test_framework.contracts.unit.supervisor.common import (
    SupervisorContractTest,
    balance_dimensions,
)
from inception_sdk.vault.contracts.supervisor.types_extension import (
    Rejected,
    Tside,
    Balance,
    BalanceDefaultDict,
    BalancesObservation,
)

# other
import library.features.lending.addresses as addresses
import library.features.lending.credit_limit as credit_limit


BALANCE_FETCHER_ID = "live_balances"
DEFAULT_DIMENSIONS = balance_dimensions()
INTERNAL_CONTRA_DIMENSIONS = balance_dimensions(address=addresses.INTERNAL_CONTRA)
PRINCIPAL_DIMENSIONS = balance_dimensions(address=addresses.PRINCIPAL)
PRINCIPAL_DUE_DIMENSIONS = balance_dimensions(address=addresses.PRINCIPAL_DUE)
PRINCIPAL_OVERDUE_DIMENSIONS = balance_dimensions(address=addresses.PRINCIPAL_OVERDUE)
NON_REPAYABLE_DIMENSIONS = balance_dimensions(address="NON_REPAYABLE_ADDRESS")


class TestCreditLimitNoUnassociatedLoans(SupervisorContractTest):
    target_test_file = "library/features/lending/credit_limit.py"
    side = Tside.ASSET

    @classmethod
    def setUpClass(cls) -> None:

        # Setup for
        loc_balances = BalanceDefaultDict(
            lambda: Balance(net=Decimal("0")),
            {
                # This represents 2 drawdowns for 400 and a repayment of 300/loan
                # the interest/principal proportion is determined by the loan balances
                DEFAULT_DIMENSIONS: Balance(net=Decimal("200")),
            },
        )

        loc_balance_observation_fetcher_mapping = {
            BALANCE_FETCHER_ID: BalancesObservation(balances=loc_balances)
        }

        cls.loc_vault_outstanding_principal = cls.create_supervisee_mock(
            SupervisorContractTest(),
            balances_observation_fetchers_mapping=loc_balance_observation_fetcher_mapping,
            **{
                "denomination": "GBP",
                credit_limit.CREDIT_LIMIT_PARAM: Decimal("1000"),
            },
        )

        # 150 outstanding per loan and 300 repayment (250 princ repayment, 50 int repayment)
        loan_balances = BalanceDefaultDict(
            lambda: Balance(net=Decimal("0")),
            {
                PRINCIPAL_DIMENSIONS: Balance(net=Decimal("50")),
                PRINCIPAL_DUE_DIMENSIONS: Balance(net=Decimal("50")),
                PRINCIPAL_OVERDUE_DIMENSIONS: Balance(net=Decimal("50")),
                NON_REPAYABLE_DIMENSIONS: Balance(net=Decimal("50")),
                # Nets off with non-repayable and then contains repayments so-50 + 300
                INTERNAL_CONTRA_DIMENSIONS: Balance(net=Decimal("250")),
            },
        )

        loan_balance_observation_fetcher_mapping = {
            BALANCE_FETCHER_ID: BalancesObservation(balances=loan_balances)
        }
        cls.loan_vaults = [
            cls.create_supervisee_mock(
                SupervisorContractTest(),
                balances_observation_fetchers_mapping=loan_balance_observation_fetcher_mapping,
                **{"principal": Decimal("400")},
            )
            for _ in range(2)
        ]
        super().setUpClass()

    def test_credit_limit_accepts_drawdowns_under_limit_outstanding_principal(self):

        posting = self.outbound_hard_settlement(amount=100, denomination="GBP")
        self.assertIsNone(
            credit_limit.validate(
                self.loc_vault_outstanding_principal,
                loans=self.loan_vaults,
                posting=posting,
                observation_fetcher_id=BALANCE_FETCHER_ID,
                denomination="GBP",
                non_repayable_addresses=["NON_REPAYABLE_ADDRESS"],
            )
        )

    def test_credit_limit_accepts_drawdowns_at_limit_outstanding_principal(self):

        posting = self.outbound_hard_settlement(amount=700, denomination="GBP")
        self.assertIsNone(
            credit_limit.validate(
                self.loc_vault_outstanding_principal,
                loans=self.loan_vaults,
                posting=posting,
                observation_fetcher_id=BALANCE_FETCHER_ID,
                denomination="GBP",
                non_repayable_addresses=["NON_REPAYABLE_ADDRESS"],
            )
        )

    def test_credit_limit_rejects_drawdowns_over_limit_outstanding_principal(self):

        posting = self.outbound_hard_settlement(amount=701, denomination="GBP")
        with self.assertRaises(Rejected) as ctx:
            self.assertIsNone(
                credit_limit.validate(
                    self.loc_vault_outstanding_principal,
                    loans=self.loan_vaults,
                    posting=posting,
                    observation_fetcher_id=BALANCE_FETCHER_ID,
                    denomination="GBP",
                    non_repayable_addresses=["NON_REPAYABLE_ADDRESS"],
                )
            )
        self.assertEqual(
            ctx.exception.message,
            "Attempted drawdown 701 GBP exceeds the remaining limit of 700.00 GBP, "
            "based on outstanding principal",
        )


class TestCreditLimitUnassociatedLoans(SupervisorContractTest):
    target_test_file = "library/features/lending/credit_limit.py"
    side = Tside.ASSET

    @classmethod
    def setUpClass(cls) -> None:

        # Setup for
        loc_balances = BalanceDefaultDict(
            lambda: Balance(net=Decimal("0")),
            {
                # This represents 2 drawdowns for 400 and a repayment of 300/loan
                # the interest/principal proportion is determined by the loan balances
                # + an unassociated loan for 100
                DEFAULT_DIMENSIONS: Balance(net=Decimal("300")),
            },
        )

        loc_balance_observation_fetcher_mapping = {
            BALANCE_FETCHER_ID: BalancesObservation(balances=loc_balances)
        }

        cls.loc_vault_outstanding_principal = cls.create_supervisee_mock(
            SupervisorContractTest(),
            balances_observation_fetchers_mapping=loc_balance_observation_fetcher_mapping,
            **{
                "denomination": "GBP",
                credit_limit.CREDIT_LIMIT_PARAM: Decimal("1000"),
            },
        )

        # 150 outstanding per loan and 300 repayment (250 princ repayment, 50 int repayment)
        loan_balances = BalanceDefaultDict(
            lambda: Balance(net=Decimal("0")),
            {
                PRINCIPAL_DIMENSIONS: Balance(net=Decimal("50")),
                PRINCIPAL_DUE_DIMENSIONS: Balance(net=Decimal("50")),
                PRINCIPAL_OVERDUE_DIMENSIONS: Balance(net=Decimal("50")),
                NON_REPAYABLE_DIMENSIONS: Balance(net=Decimal("50")),
                # Nets off with non-repayable and then contains repayments so-50 + 300
                INTERNAL_CONTRA_DIMENSIONS: Balance(net=Decimal("250")),
            },
        )

        loan_balance_observation_fetcher_mapping = {
            BALANCE_FETCHER_ID: BalancesObservation(balances=loan_balances)
        }
        cls.loan_vaults = [
            cls.create_supervisee_mock(
                SupervisorContractTest(),
                balances_observation_fetchers_mapping=loan_balance_observation_fetcher_mapping,
                **{"principal": Decimal("400")},
            )
            for _ in range(2)
        ]
        super().setUpClass()

    def test_credit_limit_accepts_drawdowns_under_limit_outstanding_principal(self):

        posting = self.outbound_hard_settlement(amount=50, denomination="GBP")
        self.assertIsNone(
            credit_limit.validate(
                self.loc_vault_outstanding_principal,
                loans=self.loan_vaults,
                posting=posting,
                observation_fetcher_id=BALANCE_FETCHER_ID,
                denomination="GBP",
                non_repayable_addresses=["NON_REPAYABLE_ADDRESS"],
            )
        )

    def test_credit_limit_accepts_drawdowns_at_limit_outstanding_principal(self):

        posting = self.outbound_hard_settlement(amount=600, denomination="GBP")
        self.assertIsNone(
            credit_limit.validate(
                self.loc_vault_outstanding_principal,
                loans=self.loan_vaults,
                posting=posting,
                observation_fetcher_id=BALANCE_FETCHER_ID,
                denomination="GBP",
                non_repayable_addresses=["NON_REPAYABLE_ADDRESS"],
            )
        )

    def test_credit_limit_rejects_drawdowns_over_limit_outstanding_principal(self):

        posting = self.outbound_hard_settlement(amount=601, denomination="GBP")
        with self.assertRaises(Rejected) as ctx:
            self.assertIsNone(
                credit_limit.validate(
                    self.loc_vault_outstanding_principal,
                    loans=self.loan_vaults,
                    posting=posting,
                    observation_fetcher_id=BALANCE_FETCHER_ID,
                    denomination="GBP",
                    non_repayable_addresses=["NON_REPAYABLE_ADDRESS"],
                )
            )
        self.assertEqual(
            ctx.exception.message,
            "Attempted drawdown 601 GBP exceeds the remaining limit of 600.00 GBP, "
            "based on outstanding principal",
        )
