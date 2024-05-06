# standard library
from datetime import datetime
from decimal import Decimal

# inception imports
from inception_sdk.test_framework.contracts.unit.common import (
    balance_dimensions,
    Balance,
    ContractFeatureTest,
    Tside,
)

from inception_sdk.vault.contracts.supervisor.types_extension import (
    BalancesObservation,
    EventTypeSchedule,
)

from inception_sdk.test_framework.contracts.unit.supervisor.common import (
    SupervisorContractTest,
    BalanceDefaultDict,
)

from library.features.common.supervisor_utils import (
    sort_supervisees,
    get_supervisees_for_alias,
    create_supervisor_event_type_schedule_from_datetime,
    sum_balances_across_supervisees,
)

DEFAULT_DATE = datetime(2019, 1, 1)
DENOMINATION = "GBP"


class TestSupervisorUtils(ContractFeatureTest):
    target_test_file = "library/features/common/supervisor_utils.py"
    side = Tside.ASSET
    default_denom = DENOMINATION

    def setUp(self) -> None:
        self.vault = self.create_mock()
        return super().setUp()

    def account_balances(
        self,
        dt=DEFAULT_DATE,
        address_1=Decimal("0"),
        address_2=Decimal("0"),
    ) -> list[tuple[datetime, BalanceDefaultDict]]:

        balance_dict = {
            balance_dimensions(address="address_1"): Balance(net=address_1),
            balance_dimensions(address="address_2"): Balance(net=address_2),
        }

        balance_default_dict = BalanceDefaultDict(lambda: Balance(net=Decimal("0")), balance_dict)

        return [(dt, balance_default_dict)]

    def test_sort_supervisees(self):

        mock_loan_1 = self.create_mock(
            account_id="loan_1", creation_date=datetime(2012, 1, 9, 0, 0)
        )
        mock_loan_2 = self.create_mock(
            account_id="loan_2", creation_date=datetime(2013, 1, 9, 0, 0)
        )
        mock_loan_3 = self.create_mock(
            account_id="loan_3", creation_date=datetime(2014, 1, 9, 0, 0)
        )
        # loan_0 has the same datetime as loan_3 but should be sorted
        # alphanumerically before loan_3
        mock_loan_0 = self.create_mock(
            account_id="loan_0", creation_date=datetime(2014, 1, 9, 0, 0)
        )

        mock_supervisees = [mock_loan_2, mock_loan_3, mock_loan_0, mock_loan_1]

        expected_list = [
            mock_loan_1,
            mock_loan_2,
            mock_loan_0,
            mock_loan_3,
        ]

        results = sort_supervisees(mock_supervisees)

        self.assertEqual(results, expected_list)

    def test_sum_balances_across_supervisees_with_regular_fetchers(self):
        supervisee_1 = self.create_mock(
            balance_ts=self.account_balances(
                address_1=Decimal("1.0123"), address_2=Decimal("1.0123")
            )
        )
        supervisee_2 = self.create_mock(
            balance_ts=self.account_balances(
                address_1=Decimal("0.0123"), address_2=Decimal("0.0123")
            )
        )
        balance_sum = sum_balances_across_supervisees(
            supervisees=[supervisee_1, supervisee_2],
            addresses=["address_1", "address_2"],
            denomination=self.default_denom,
            rounding_precision=3,
        )
        self.assertEqual(balance_sum, Decimal("2.050"))

    def test_sum_balances_across_supervisees_with_observation_fetchers(self):

        account_1_observation = BalancesObservation(
            balances=self.account_balances(
                address_1=Decimal("1.0123"), address_2=Decimal("1.0123")
            )[0][1]
        )
        account_2_observation = BalancesObservation(
            balances=self.account_balances(
                address_1=Decimal("0.0123"), address_2=Decimal("0.0123")
            )[0][1]
        )

        supervisee_1 = self.create_mock(
            balances_observation_fetchers_mapping={"optimised_fetcher": account_1_observation}
        )
        supervisee_2 = self.create_mock(
            balances_observation_fetchers_mapping={"optimised_fetcher": account_2_observation}
        )
        balance_sum = sum_balances_across_supervisees(
            supervisees=[supervisee_1, supervisee_2],
            addresses=["address_1", "address_2"],
            denomination=self.default_denom,
            observation_fetcher_id="optimised_fetcher",
            rounding_precision=3,
        )
        self.assertEqual(balance_sum, Decimal("2.050"))


class TestGetAliasMethod(SupervisorContractTest):
    contract_files = {
        "supervisor": "library/line_of_credit/supervisors/template/line_of_credit_supervisor.py",
        "loan": "library/line_of_credit/contracts/template/drawdown_loan.py",
        "loc": "library/line_of_credit/contracts/template/line_of_credit.py",
    }

    def test_get_supervisees_for_alias_returns_correct_list_with_same_creation_date(
        self,
    ):
        mock_vault_supervisee_1 = self.create_supervisee_mock(alias="loan", account_id="000001")
        mock_vault_supervisee_2 = self.create_supervisee_mock(alias="loan", account_id="000002")
        mock_vault_supervisee_3 = self.create_supervisee_mock(alias="loc", account_id="000003")

        supervisees = {
            "000001": mock_vault_supervisee_1,
            "000002": mock_vault_supervisee_2,
            "000003": mock_vault_supervisee_3,
        }

        expected = [mock_vault_supervisee_1, mock_vault_supervisee_2]

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        results = get_supervisees_for_alias(mock_vault, "loan")

        self.assertEqual(results, expected)

    def test_get_supervisees_for_alias_returns_correctly_ordered_list_with_different_dates(
        self,
    ):
        mock_vault_loan_1 = self.create_supervisee_mock(
            alias="loan", account_id="000001", creation_date=datetime(2020, 1, 1)
        )
        mock_vault_loan_2 = self.create_supervisee_mock(
            alias="loan", account_id="000002", creation_date=datetime(2019, 1, 1)
        )
        mock_vault_loan_3 = self.create_supervisee_mock(
            alias="loan", account_id="000004", creation_date=datetime(2020, 1, 1)
        )
        mock_vault_loan_4 = self.create_supervisee_mock(
            alias="loan", account_id="000005", creation_date=datetime(2019, 1, 1)
        )
        mock_vault_loc_1 = self.create_supervisee_mock(
            alias="loc", account_id="000006", creation_date=datetime(2020, 5, 10)
        )
        supervisees = {
            "000002": mock_vault_loan_2,
            "000001": mock_vault_loan_1,
            "000004": mock_vault_loan_3,
            "000005": mock_vault_loan_4,
            "000006": mock_vault_loc_1,
        }

        expected = [mock_vault_loan_2, mock_vault_loan_4, mock_vault_loan_1, mock_vault_loan_3]

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        results = get_supervisees_for_alias(mock_vault, "loan")

        self.assertEqual(results, expected)

    def test_get_supervisees_for_alias_returns_empty_list_when_no_matching_alias(self):
        mock_vault_loan_1 = self.create_supervisee_mock(alias="loan", account_id="000001")
        mock_vault_loan_2 = self.create_supervisee_mock(alias="loan", account_id="000002")
        mock_vault_loc_1 = self.create_supervisee_mock(alias="loc", account_id="000003")
        supervisees = {
            "000001": mock_vault_loan_1,
            "000002": mock_vault_loan_2,
            "000003": mock_vault_loc_1,
        }

        expected = []

        mock_vault = self.create_supervisor_mock(supervisees=supervisees)
        results = get_supervisees_for_alias(mock_vault, "wrong_alias")

        self.assertEqual(results, expected)

    def test_get_supervisees_for_alias_returns_empty_list_with_no_supervisees(self):
        expected = []

        mock_vault = self.create_supervisor_mock(supervisees={})
        results = get_supervisees_for_alias(mock_vault, "loan")

        self.assertEqual(results, expected)

    def test_create_supervisor_event_type_schedule_from_datetime(self):
        schedule_datetime = datetime(year=2000, month=1, day=2, hour=3, minute=4, second=5)
        expected_event_type_schedule = EventTypeSchedule(
            day="2", hour="3", minute="4", second="5", month="1", year="2000"
        )
        result = create_supervisor_event_type_schedule_from_datetime(schedule_datetime)

        self.assertEqual(result.__dict__, expected_event_type_schedule.__dict__)
