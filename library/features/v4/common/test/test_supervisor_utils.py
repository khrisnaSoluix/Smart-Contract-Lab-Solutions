# standard libs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# features
import library.features.v4.common.addresses as addresses
import library.features.v4.common.supervisor_utils as supervisor_utils

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    BalanceTimeseries,
    Phase,
    Posting,
    SupervisorScheduledEventHookArguments,
    Tside,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    CustomInstruction,
    ScheduledEvent,
    ScheduledEventHookResult,
    SupervisorContractEventType,
    UpdatePlanEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelAccountNotificationDirective,
    SentinelBalance,
    SentinelBalancesObservation,
    SentinelPosting,
    SentinelPostingInstructionsDirective,
    SentinelScheduleExpression,
    SentinelUpdateAccountEventTypeDirective,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.supervisor.common import (
    DEFAULT_DATETIME,
    SupervisorFeatureTest,
)

DECIMAL_ZERO = Decimal("0")
DEFAULT_DENOMINATION = "GBP"
DEFAULT_COORDINATE = BalanceCoordinate(
    DEFAULT_ADDRESS, DEFAULT_ASSET, DEFAULT_DENOMINATION, Phase.COMMITTED
)


class GetSuperviseesForAliasTest(SupervisorFeatureTest):
    @patch.object(supervisor_utils, "sort_supervisees")
    def test_get_supervisees_for_alias_sorts_only_given_alias_vault_objects(
        self, mock_sort_supervisees: MagicMock
    ):
        # construct mocks
        mock_vault_loan_1 = self.create_supervisee_mock(supervisee_alias="loan", account_id="001")
        mock_vault_loan_2 = self.create_supervisee_mock(supervisee_alias="loan", account_id="002")
        mock_vault_loc_3 = self.create_supervisee_mock(supervisee_alias="loc", account_id="003")

        supervisees = {
            "001": mock_vault_loan_1,
            "002": mock_vault_loan_2,
            "003": mock_vault_loc_3,
        }

        mock_supervisor_vault = self.create_supervisor_mock(supervisees=supervisees)
        mock_sort_supervisees.return_value = sentinel.sorted_supervisees

        # construct expected result
        # N.B. these are in the original order
        expected_loan_vault_objects = [mock_vault_loan_1, mock_vault_loan_2]

        # run function
        result = supervisor_utils.get_supervisees_for_alias(mock_supervisor_vault, "loan")
        self.assertEqual(result, sentinel.sorted_supervisees)
        mock_sort_supervisees.assert_called_once_with(expected_loan_vault_objects)

    @patch.object(supervisor_utils, "sort_supervisees")
    def test_get_supervisees_for_alias_sorts_empty_list_when_no_matching_alias(
        self, mock_sort_supervisees: MagicMock
    ):
        # construct mocks
        mock_vault_loan_1 = self.create_supervisee_mock(supervisee_alias="loan", account_id="001")
        mock_vault_loan_2 = self.create_supervisee_mock(supervisee_alias="loan", account_id="002")
        mock_vault_loc_1 = self.create_supervisee_mock(supervisee_alias="loc", account_id="003")
        supervisees = {
            "001": mock_vault_loan_1,
            "002": mock_vault_loan_2,
            "003": mock_vault_loc_1,
        }

        mock_supervisor_vault = self.create_supervisor_mock(supervisees=supervisees)
        mock_sort_supervisees.return_value = []

        # run function
        result = supervisor_utils.get_supervisees_for_alias(mock_supervisor_vault, "wrong_alias")
        self.assertEqual(result, [])
        mock_sort_supervisees.assert_called_once_with([])

    @patch.object(supervisor_utils, "sort_supervisees")
    def test_get_supervisees_for_alias_sorts_empty_list_with_no_supervisees(
        self, mock_sort_supervisees: MagicMock
    ):
        # construct mocks
        mock_supervisor_vault = self.create_supervisor_mock(supervisees={})
        mock_sort_supervisees.return_value = []

        # run function
        result = supervisor_utils.get_supervisees_for_alias(mock_supervisor_vault, "loan")
        self.assertListEqual(result, [])
        mock_sort_supervisees.assert_called_once_with([])

    def test_sort_supervisees_returns_correct_list_with_same_creation_date(self):
        # construct mocks
        mock_s1 = self.create_supervisee_mock(account_id="s1")
        mock_s2 = self.create_supervisee_mock(account_id="s2")
        mock_s3 = self.create_supervisee_mock(account_id="s3")

        # construct expected result
        expected_list = [mock_s1, mock_s2, mock_s3]

        # run function
        result = supervisor_utils.sort_supervisees([mock_s2, mock_s3, mock_s1])
        self.assertListEqual(result, expected_list)

    def test_sort_supervisees_with_different_dates(self):
        # construct mocks
        mock_s1 = self.create_supervisee_mock(
            account_id="s1", creation_date=datetime(2012, 1, 9, 0, 0)
        )
        mock_s2 = self.create_supervisee_mock(
            account_id="s2", creation_date=datetime(2013, 1, 9, 0, 0)
        )
        mock_s3 = self.create_supervisee_mock(
            account_id="s3", creation_date=datetime(2014, 1, 9, 0, 0)
        )
        # s0 has the same datetime as s3 but should be sorted
        # alphanumerically before s3
        mock_s0 = self.create_supervisee_mock(
            account_id="s0", creation_date=datetime(2014, 1, 9, 0, 0)
        )

        # construct expected result
        expected_list = [mock_s1, mock_s2, mock_s0, mock_s3]

        # run function
        result = supervisor_utils.sort_supervisees([mock_s2, mock_s3, mock_s0, mock_s1])
        self.assertListEqual(result, expected_list)

    def test_sort_supervisees_returns_empty_list_for_empty_list(self):
        # run function
        result = supervisor_utils.sort_supervisees([])
        self.assertListEqual(result, [])


class GetBalanceDefaultDictsForSuperviseesTest(SupervisorFeatureTest):
    def test_correct_balance_default_dict_list_is_returned(
        self,
    ):
        fetcher_id = sentinel.fetcher_id

        bof_mapping_1 = {
            sentinel.fetcher_id: SentinelBalancesObservation("balances1"),
        }
        bof_mapping_2 = {
            sentinel.fetcher_id: SentinelBalancesObservation("balances2"),
        }
        bof_mapping_3 = {
            sentinel.fetcher_id: SentinelBalancesObservation("balances3"),
        }

        mock_s1 = self.create_supervisee_mock(
            account_id="s1", balances_observation_fetchers_mapping=bof_mapping_1
        )
        mock_s2 = self.create_supervisee_mock(
            account_id="s2", balances_observation_fetchers_mapping=bof_mapping_2
        )
        mock_s3 = self.create_supervisee_mock(
            account_id="s3", balances_observation_fetchers_mapping=bof_mapping_3
        )
        supervisee_list = [mock_s1, mock_s2, mock_s3]

        expected = [
            SentinelBalancesObservation("balances1").balances,
            SentinelBalancesObservation("balances2").balances,
            SentinelBalancesObservation("balances3").balances,
        ]

        result = supervisor_utils.get_balance_default_dicts_for_supervisees(
            supervisees=supervisee_list,
            fetcher_id=fetcher_id,
        )

        self.assertEqual(result, expected)


@patch.object(supervisor_utils.utils, "get_balance_default_dict_from_mapping")
class GetBalanceDefaultDictFromTimeseriesTest(SupervisorFeatureTest):
    def test_correct_balance_default_dict_list_is_returned(
        self, mock_get_balance_default_dict_from_mapping: MagicMock
    ):
        mock_get_balance_default_dict_from_mapping.side_effect = [
            sentinel.s1_balance_default_dict,
            sentinel.s2_balance_default_dict,
            sentinel.s3_balance_default_dict,
        ]

        mock_s1 = self.create_supervisee_mock(
            account_id="s1",
            requires_fetched_balances={
                DEFAULT_COORDINATE: BalanceTimeseries(
                    [(DEFAULT_DATETIME, sentinel.s1_balance_default_dict)]
                )
            },
        )
        mock_s2 = self.create_supervisee_mock(
            account_id="s2",
            requires_fetched_balances={
                DEFAULT_COORDINATE: BalanceTimeseries(
                    [(DEFAULT_DATETIME, sentinel.s2_balance_default_dict)]
                )
            },
        )
        mock_s3 = self.create_supervisee_mock(
            account_id="s3",
            requires_fetched_balances={
                DEFAULT_COORDINATE: BalanceTimeseries(
                    [(DEFAULT_DATETIME, sentinel.s3_balance_default_dict)]
                )
            },
        )
        supervisee_list = [mock_s1, mock_s2, mock_s3]

        expected_result = {
            mock_s1.account_id: sentinel.s1_balance_default_dict,
            mock_s2.account_id: sentinel.s2_balance_default_dict,
            mock_s3.account_id: sentinel.s3_balance_default_dict,
        }

        result = supervisor_utils.get_balances_default_dicts_from_timeseries(
            supervisees=supervisee_list, effective_datetime=DEFAULT_DATETIME
        )

        self.assertEqual(result, expected_result)


class SumBalancesAcrossSuperviseesTest(SupervisorFeatureTest):
    @patch.object(supervisor_utils.utils, "sum_balances")
    def test_correct_sum_is_returned(
        self,
        mock_sum_balances: MagicMock,
    ):
        denomination = sentinel.denomination
        addresses = [sentinel.address]
        balances = [
            SentinelBalance("balance1"),
            SentinelBalance("balance2"),
            SentinelBalance("balance3"),
        ]
        mock_sum_balances.side_effect = [Decimal("5.23"), Decimal("9.82"), Decimal("14.77")]

        expected = Decimal("29.82")

        result = supervisor_utils.sum_balances_across_supervisees(
            denomination=denomination,
            addresses=addresses,
            balances=balances,
        )

        self.assertEqual(result, expected)

    @patch.object(supervisor_utils.utils, "sum_balances")
    def test_rounding_occurs_on_each_supervisee_balance(
        self,
        mock_sum_balances: MagicMock,
    ):
        denomination = sentinel.denomination
        addresses = [sentinel.address]
        balances = [
            SentinelBalance("balance1"),
            SentinelBalance("balance2"),
            SentinelBalance("balance3"),
        ]
        mock_sum_balances.side_effect = [Decimal("5.235"), Decimal("9.825"), Decimal("14.775")]

        expected = Decimal("29.85")

        result = supervisor_utils.sum_balances_across_supervisees(
            denomination=denomination,
            addresses=addresses,
            balances=balances,
        )

        self.assertEqual(result, expected)


class GetSuperviseeMappingTest(SupervisorFeatureTest):
    def test_blank_dict_returned_when_no_directives(self):
        # construct mocks
        supervisee_vault = self.create_supervisee_mock(
            supervisee_hook_result=ScheduledEventHookResult(),
            account_id="supervisee",
        )

        # construct expected result
        expected_result = ({}, {}, {})

        # run function
        result = supervisor_utils.get_supervisee_directives_mapping(supervisee_vault)
        self.assertTupleEqual(result, expected_result)

    def test_only_posting_dict_returned_when_only_posting_directives_present(self):
        # construct mocks
        supervisee_vault = self.create_supervisee_mock(
            supervisee_hook_result=ScheduledEventHookResult(
                posting_instructions_directives=[SentinelPostingInstructionsDirective("pid")]
            ),
            account_id="supervisee",
        )

        # construct expected result
        expected_result = ({}, {"supervisee": [SentinelPostingInstructionsDirective("pid")]}, {})

        # run function
        result = supervisor_utils.get_supervisee_directives_mapping(supervisee_vault)

        self.assertTupleEqual(result, expected_result)

    def test_only_notification_dict_returned_when_only_notification_directives_present(self):
        # construct mocks
        supervisee_vault = self.create_supervisee_mock(
            supervisee_hook_result=ScheduledEventHookResult(
                account_notification_directives=[SentinelAccountNotificationDirective("anid")]
            ),
            account_id="supervisee",
        )

        # construct expected result
        expected_result = ({"supervisee": [SentinelAccountNotificationDirective("anid")]}, {}, {})

        # run function
        result = supervisor_utils.get_supervisee_directives_mapping(supervisee_vault)

        self.assertTupleEqual(result, expected_result)

    def test_only_update_plan_event_dict_returned_when_only_update_plan_event_directives_present(
        self,
    ):
        # construct mocks
        supervisee_vault = self.create_supervisee_mock(
            supervisee_hook_result=ScheduledEventHookResult(
                update_account_event_type_directives=[
                    SentinelUpdateAccountEventTypeDirective("uaetid")
                ]
            ),
            account_id="supervisee",
        )

        # construct expected result
        expected_result = (
            {},
            {},
            {"supervisee": [SentinelUpdateAccountEventTypeDirective("uaetid")]},
        )

        # run function
        result = supervisor_utils.get_supervisee_directives_mapping(supervisee_vault)

        self.assertTupleEqual(result, expected_result)

    def test_all_directives_returned(self):
        # construct mocks
        supervisee_vault = self.create_supervisee_mock(
            supervisee_hook_result=ScheduledEventHookResult(
                account_notification_directives=[SentinelAccountNotificationDirective("anid")],
                posting_instructions_directives=[SentinelPostingInstructionsDirective("pid")],
                update_account_event_type_directives=[
                    SentinelUpdateAccountEventTypeDirective("uaetid")
                ],
            ),
            account_id="supervisee",
        )

        # construct expected result
        expected_result = (
            {"supervisee": [SentinelAccountNotificationDirective("anid")]},
            {"supervisee": [SentinelPostingInstructionsDirective("pid")]},
            {"supervisee": [SentinelUpdateAccountEventTypeDirective("uaetid")]},
        )

        # run function
        result = supervisor_utils.get_supervisee_directives_mapping(supervisee_vault)

        self.assertTupleEqual(result, expected_result)


@patch.object(supervisor_utils, "filter_aggregate_balances")
@patch.object(supervisor_utils.utils, "create_postings")
class CreateAggregatePostingInstructionsTest(SupervisorFeatureTest):
    def test_no_posting_instructions_returned_when_there_are_no_postings_to_aggregate(
        self,
        mock_create_postings: MagicMock,
        mock_filter_aggregate_balances: MagicMock,
    ):
        mock_filter_aggregate_balances.return_value = {}

        result = supervisor_utils.create_aggregate_posting_instructions(
            aggregate_account_id=sentinel.account_id,
            posting_instructions_by_supervisee={},
            prefix=sentinel.prefix,
            balances=sentinel.balances,
            addresses_to_aggregate=sentinel.addresses_to_aggregate,
        )

        self.assertListEqual(result, [])
        mock_filter_aggregate_balances.assert_called_once_with(
            aggregate_balances={},
            balances=sentinel.balances,
            addresses_to_aggregate=sentinel.addresses_to_aggregate,
            rounding_precision=2,
        )
        mock_create_postings.assert_not_called()

    def test_asset_posting_instructions_are_returned_correctly(
        self,
        mock_create_postings: MagicMock,
        mock_filter_aggregate_balances: MagicMock,
    ):
        posting_for_instruction_1 = [
            Posting(
                credit=True,
                amount=Decimal("10"),
                denomination=self.default_denomination,
                account_id="default_account",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        posting_for_instruction_2 = [
            Posting(
                credit=False,
                amount=Decimal("100"),
                denomination=self.default_denomination,
                account_id="default_account",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        posting_for_instruction_3 = [
            Posting(
                credit=True,
                amount=Decimal("50"),
                denomination=self.default_denomination,
                account_id="default_account",
                account_address=addresses.PENALTIES,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]

        posting_instructions = {
            "default_account": [
                self.custom_instruction(postings=posting_for_instruction_1),
                self.custom_instruction(postings=posting_for_instruction_2),
                self.custom_instruction(postings=posting_for_instruction_3),
            ]
        }

        mock_filter_aggregate_balances.return_value = {
            BalanceCoordinate(
                account_address=sentinel.account_address_1,
                asset=sentinel.asset_1,
                denomination=sentinel.denomination_1,
                phase=sentinel.phase_1,
            ): Balance(credit=sentinel.credit, debit=sentinel.debit, net=Decimal("90")),
            BalanceCoordinate(
                account_address=sentinel.account_address_2,
                asset=sentinel.asset_2,
                denomination=sentinel.denomination_2,
                phase=sentinel.phase_2,
            ): Balance(credit=sentinel.credit, debit=sentinel.debit, net=Decimal("-50")),
        }

        mock_create_postings.return_value = [SentinelPosting("dummy_posting")]

        result = supervisor_utils.create_aggregate_posting_instructions(
            aggregate_account_id=sentinel.account_id,
            posting_instructions_by_supervisee=posting_instructions,
            prefix=sentinel.prefix,
            balances=sentinel.balances,
            addresses_to_aggregate=sentinel.addresses_to_aggregate,
        )

        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=[SentinelPosting("dummy_posting"), SentinelPosting("dummy_posting")],
                    instruction_details={"force_override": "true"},
                )
            ],
        )
        mock_filter_aggregate_balances.assert_called_once_with(
            aggregate_balances={
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination=self.default_denomination,
                    phase=Phase.COMMITTED,
                ): Balance(credit=Decimal("10"), debit=Decimal("100"), net=Decimal("90")),
                BalanceCoordinate(
                    account_address=addresses.PENALTIES,
                    asset=DEFAULT_ASSET,
                    denomination=self.default_denomination,
                    phase=Phase.COMMITTED,
                ): Balance(credit=Decimal("50"), debit=Decimal("0"), net=Decimal("-50")),
            },
            balances=sentinel.balances,
            addresses_to_aggregate=sentinel.addresses_to_aggregate,
            rounding_precision=2,
        )
        mock_create_postings.assert_has_calls(
            [
                call(
                    amount=Decimal("90"),
                    debit_account=sentinel.account_id,
                    credit_account=sentinel.account_id,
                    debit_address="sentinel.prefix_sentinel.account_address_1",
                    credit_address=addresses.INTERNAL_CONTRA,
                    denomination=sentinel.denomination_1,
                    asset=sentinel.asset_1,
                ),
                call(
                    amount=Decimal("50"),
                    debit_account=sentinel.account_id,
                    credit_account=sentinel.account_id,
                    debit_address=addresses.INTERNAL_CONTRA,
                    credit_address="sentinel.prefix_sentinel.account_address_2",
                    denomination=sentinel.denomination_2,
                    asset=sentinel.asset_2,
                ),
            ]
        )

    def test_liability_posting_instructions_are_returned_correctly(
        self,
        mock_create_postings: MagicMock,
        mock_filter_aggregate_balances: MagicMock,
    ):
        posting_for_instruction_1 = [
            Posting(
                credit=True,
                amount=Decimal("10"),
                denomination=self.default_denomination,
                account_id="default_account",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        posting_for_instruction_2 = [
            Posting(
                credit=False,
                amount=Decimal("100"),
                denomination=self.default_denomination,
                account_id="default_account",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        posting_for_instruction_3 = [
            Posting(
                credit=True,
                amount=Decimal("50"),
                denomination=self.default_denomination,
                account_id="default_account",
                account_address=addresses.PENALTIES,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]

        posting_instructions = posting_instructions = {
            "default_account": [
                self.custom_instruction(postings=posting_for_instruction_1),
                self.custom_instruction(postings=posting_for_instruction_2),
                self.custom_instruction(postings=posting_for_instruction_3),
            ]
        }

        mock_filter_aggregate_balances.return_value = {
            BalanceCoordinate(
                account_address=sentinel.account_address_1,
                asset=sentinel.asset_1,
                denomination=sentinel.denomination_1,
                phase=sentinel.phase_1,
            ): Balance(credit=sentinel.credit, debit=sentinel.debit, net=Decimal("-90")),
            BalanceCoordinate(
                account_address=sentinel.account_address_2,
                asset=sentinel.asset_2,
                denomination=sentinel.denomination_2,
                phase=sentinel.phase_2,
            ): Balance(credit=sentinel.credit, debit=sentinel.debit, net=Decimal("50")),
        }

        mock_create_postings.return_value = [SentinelPosting("dummy_posting")]

        result = supervisor_utils.create_aggregate_posting_instructions(
            aggregate_account_id=sentinel.account_id,
            posting_instructions_by_supervisee=posting_instructions,
            prefix=sentinel.prefix,
            balances=sentinel.balances,
            addresses_to_aggregate=sentinel.addresses_to_aggregate,
            tside=Tside.LIABILITY,
        )

        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=[SentinelPosting("dummy_posting"), SentinelPosting("dummy_posting")],
                    instruction_details={"force_override": "true"},
                )
            ],
        )
        mock_filter_aggregate_balances.assert_called_once_with(
            aggregate_balances={
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination=self.default_denomination,
                    phase=Phase.COMMITTED,
                ): Balance(credit=Decimal("10"), debit=Decimal("100"), net=Decimal("-90")),
                BalanceCoordinate(
                    account_address=addresses.PENALTIES,
                    asset=DEFAULT_ASSET,
                    denomination=self.default_denomination,
                    phase=Phase.COMMITTED,
                ): Balance(credit=Decimal("50"), debit=Decimal("0"), net=Decimal("50")),
            },
            balances=sentinel.balances,
            addresses_to_aggregate=sentinel.addresses_to_aggregate,
            rounding_precision=2,
        )
        mock_create_postings.assert_has_calls(
            [
                call(
                    amount=Decimal("90"),
                    debit_account=sentinel.account_id,
                    credit_account=sentinel.account_id,
                    debit_address="sentinel.prefix_sentinel.account_address_1",
                    credit_address=addresses.INTERNAL_CONTRA,
                    denomination=sentinel.denomination_1,
                    asset=sentinel.asset_1,
                ),
                call(
                    amount=Decimal("50"),
                    debit_account=sentinel.account_id,
                    credit_account=sentinel.account_id,
                    debit_address=addresses.INTERNAL_CONTRA,
                    credit_address="sentinel.prefix_sentinel.account_address_2",
                    denomination=sentinel.denomination_2,
                    asset=sentinel.asset_2,
                ),
            ]
        )

    def test_non_default_force_override_returned_correctly(
        self,
        mock_create_postings: MagicMock,
        mock_filter_aggregate_balances: MagicMock,
    ):
        posting_for_instruction_1 = [
            Posting(
                credit=True,
                amount=Decimal("10"),
                denomination=self.default_denomination,
                account_id="default_account",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        posting_for_instruction_2 = [
            Posting(
                credit=False,
                amount=Decimal("100"),
                denomination=self.default_denomination,
                account_id="default_account",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]
        posting_for_instruction_3 = [
            Posting(
                credit=True,
                amount=Decimal("50"),
                denomination=self.default_denomination,
                account_id="default_account",
                account_address=addresses.PENALTIES,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]

        posting_instructions = posting_instructions = {
            "default_account": [
                self.custom_instruction(postings=posting_for_instruction_1),
                self.custom_instruction(postings=posting_for_instruction_2),
                self.custom_instruction(postings=posting_for_instruction_3),
            ]
        }

        mock_filter_aggregate_balances.return_value = {
            BalanceCoordinate(
                account_address=sentinel.account_address_1,
                asset=sentinel.asset_1,
                denomination=sentinel.denomination_1,
                phase=sentinel.phase_1,
            ): Balance(credit=sentinel.credit, debit=sentinel.debit, net=Decimal("-90")),
            BalanceCoordinate(
                account_address=sentinel.account_address_2,
                asset=sentinel.asset_2,
                denomination=sentinel.denomination_2,
                phase=sentinel.phase_2,
            ): Balance(credit=sentinel.credit, debit=sentinel.debit, net=Decimal("50")),
        }

        mock_create_postings.return_value = [SentinelPosting("dummy_posting")]

        result = supervisor_utils.create_aggregate_posting_instructions(
            aggregate_account_id=sentinel.account_id,
            posting_instructions_by_supervisee=posting_instructions,
            prefix=sentinel.prefix,
            balances=sentinel.balances,
            addresses_to_aggregate=sentinel.addresses_to_aggregate,
            tside=Tside.LIABILITY,
            force_override=False,
        )

        self.assertListEqual(
            result,
            [
                CustomInstruction(
                    postings=[SentinelPosting("dummy_posting"), SentinelPosting("dummy_posting")],
                    instruction_details={"force_override": "false"},
                )
            ],
        )
        mock_filter_aggregate_balances.assert_called_once_with(
            aggregate_balances={
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination=self.default_denomination,
                    phase=Phase.COMMITTED,
                ): Balance(credit=Decimal("10"), debit=Decimal("100"), net=Decimal("-90")),
                BalanceCoordinate(
                    account_address=addresses.PENALTIES,
                    asset=DEFAULT_ASSET,
                    denomination=self.default_denomination,
                    phase=Phase.COMMITTED,
                ): Balance(credit=Decimal("50"), debit=Decimal("0"), net=Decimal("50")),
            },
            balances=sentinel.balances,
            addresses_to_aggregate=sentinel.addresses_to_aggregate,
            rounding_precision=2,
        )
        mock_create_postings.assert_has_calls(
            [
                call(
                    amount=Decimal("90"),
                    debit_account=sentinel.account_id,
                    credit_account=sentinel.account_id,
                    debit_address="sentinel.prefix_sentinel.account_address_1",
                    credit_address=addresses.INTERNAL_CONTRA,
                    denomination=sentinel.denomination_1,
                    asset=sentinel.asset_1,
                ),
                call(
                    amount=Decimal("50"),
                    debit_account=sentinel.account_id,
                    credit_account=sentinel.account_id,
                    debit_address=addresses.INTERNAL_CONTRA,
                    credit_address="sentinel.prefix_sentinel.account_address_2",
                    denomination=sentinel.denomination_2,
                    asset=sentinel.asset_2,
                ),
            ]
        )

    def test_non_default_rounding_precision(
        self,
        mock_create_postings: MagicMock,
        mock_filter_aggregate_balances: MagicMock,
    ):
        mock_filter_aggregate_balances.return_value = {}

        result = supervisor_utils.create_aggregate_posting_instructions(
            aggregate_account_id=sentinel.account_id,
            posting_instructions_by_supervisee={},
            prefix=sentinel.prefix,
            balances=sentinel.balances,
            addresses_to_aggregate=sentinel.addresses_to_aggregate,
            rounding_precision=3,
        )

        self.assertListEqual(result, [])
        mock_filter_aggregate_balances.assert_called_once_with(
            aggregate_balances={},
            balances=sentinel.balances,
            addresses_to_aggregate=sentinel.addresses_to_aggregate,
            rounding_precision=3,
        )
        mock_create_postings.assert_not_called()


@patch.object(supervisor_utils.utils, "round_decimal")
class FilterAggregateBalancesTest(SupervisorFeatureTest):
    def test_aggregate_balances_are_filtered_when_rounded_amounts_are_equivalent(
        self, mock_round_decimal: MagicMock
    ):
        # new rounded amount, then the latest rounded amount
        mock_round_decimal.side_effect = [
            Decimal("7"),
            Decimal("7"),
            Decimal("0.12"),
            Decimal("0.12"),
        ]

        aggregate_balance_default_dict = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0"), debit=Decimal("0"), net=Decimal("0")),
                BalanceCoordinate(
                    account_address="ACCRUED_INTEREST_RECEIVABLE",
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.001"), debit=Decimal("0"), net=Decimal("0.001")),
            }
        )

        latest_balance_default_dict = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("10"), debit=Decimal("3"), net=Decimal("7")),
                BalanceCoordinate(
                    account_address="ACCRUED_INTEREST_RECEIVABLE",
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.123"), debit=Decimal("0"), net=Decimal("0.123")),
            }
        )

        result = supervisor_utils.filter_aggregate_balances(
            aggregate_balances=aggregate_balance_default_dict,
            balances=latest_balance_default_dict,
            addresses_to_aggregate=[DEFAULT_ADDRESS, "ACCRUED_INTEREST_RECEIVABLE"],
        )

        self.assertDictEqual(result, {})
        mock_round_decimal.assert_has_calls(
            [
                call(amount=Decimal("7"), decimal_places=2),
                call(amount=Decimal("7"), decimal_places=2),
                call(amount=Decimal("0.124"), decimal_places=2),
                call(amount=Decimal("0.123"), decimal_places=2),
            ]
        )

    def test_aggregate_balances_are_not_filtered_when_rounded_amounts_are_different(
        self, mock_round_decimal: MagicMock
    ):
        # new rounded amount, then the latest rounded amount
        mock_round_decimal.side_effect = [
            Decimal("12"),
            Decimal("7"),
            Decimal("0.13"),
            Decimal("0.12"),
        ]

        aggregate_balance_default_dict = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("5"), debit=Decimal("0"), net=Decimal("5")),
                BalanceCoordinate(
                    account_address="ACCRUED_INTEREST_RECEIVABLE",
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.002"), debit=Decimal("0"), net=Decimal("0.002")),
            }
        )

        latest_balance_default_dict = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("10"), debit=Decimal("3"), net=Decimal("7")),
                BalanceCoordinate(
                    account_address="ACCRUED_INTEREST_RECEIVABLE",
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.123"), debit=Decimal("0"), net=Decimal("0.123")),
            }
        )

        result = supervisor_utils.filter_aggregate_balances(
            aggregate_balances=aggregate_balance_default_dict,
            balances=latest_balance_default_dict,
            addresses_to_aggregate=[DEFAULT_ADDRESS, "ACCRUED_INTEREST_RECEIVABLE"],
        )

        self.assertDictEqual(result, aggregate_balance_default_dict)
        mock_round_decimal.assert_has_calls(
            [
                call(amount=Decimal("12"), decimal_places=2),
                call(amount=Decimal("7"), decimal_places=2),
                call(amount=Decimal("0.125"), decimal_places=2),
                call(amount=Decimal("0.123"), decimal_places=2),
            ]
        )

    def test_filter_only_aggregate_balances_for_given_addresses(
        self, mock_round_decimal: MagicMock
    ):
        # new rounded amount, then the latest rounded amount
        # for each coordinate with address passed in
        mock_round_decimal.side_effect = [
            Decimal("0.13"),
            Decimal("0.12"),
            Decimal("0.13"),
            Decimal("0.12"),
        ]

        aggregate_balance_default_dict = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=sentinel.address_1,
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.01"), debit=Decimal("0"), net=Decimal("0.01")),
                BalanceCoordinate(
                    account_address=sentinel.address_2,
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.01"), debit=Decimal("0"), net=Decimal("0.01")),
                BalanceCoordinate(
                    account_address=sentinel.address_3,
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.01"), debit=Decimal("0"), net=Decimal("0.01")),
            }
        )

        latest_balance_default_dict = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=sentinel.address_1,
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.12"), debit=Decimal("0"), net=Decimal("0.12")),
                BalanceCoordinate(
                    account_address=sentinel.address_2,
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.12"), debit=Decimal("0"), net=Decimal("0.12")),
                BalanceCoordinate(
                    account_address=sentinel.address_3,
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.12"), debit=Decimal("0"), net=Decimal("0.12")),
            }
        )

        expected = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=sentinel.address_1,
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.01"), debit=Decimal("0"), net=Decimal("0.01")),
                BalanceCoordinate(
                    account_address=sentinel.address_3,
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.01"), debit=Decimal("0"), net=Decimal("0.01")),
            }
        )

        result = supervisor_utils.filter_aggregate_balances(
            aggregate_balances=aggregate_balance_default_dict,
            balances=latest_balance_default_dict,
            addresses_to_aggregate=[sentinel.address_1, sentinel.address_3],
        )

        self.assertDictEqual(result, expected)
        mock_round_decimal.assert_has_calls(
            [
                call(amount=Decimal("0.13"), decimal_places=2),
                call(amount=Decimal("0.12"), decimal_places=2),
                call(amount=Decimal("0.13"), decimal_places=2),
                call(amount=Decimal("0.12"), decimal_places=2),
            ]
        )

    def test_non_default_rounding_precision(self, mock_round_decimal: MagicMock):
        # new rounded amount, then the latest rounded amount
        mock_round_decimal.side_effect = [Decimal("1"), Decimal("0")]

        aggregate_balance_default_dict = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address="ACCRUED_INTEREST_RECEIVABLE",
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.4"), debit=Decimal("0"), net=Decimal("0.4")),
            }
        )

        latest_balance_default_dict = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address="ACCRUED_INTEREST_RECEIVABLE",
                    asset=sentinel.asset,
                    denomination=sentinel.denomination,
                    phase=sentinel.phase,
                ): Balance(credit=Decimal("0.1"), debit=Decimal("0"), net=Decimal("0.1")),
            }
        )

        result = supervisor_utils.filter_aggregate_balances(
            aggregate_balances=aggregate_balance_default_dict,
            balances=latest_balance_default_dict,
            addresses_to_aggregate=["ACCRUED_INTEREST_RECEIVABLE"],
            rounding_precision=0,
        )

        self.assertDictEqual(result, aggregate_balance_default_dict)
        mock_round_decimal.assert_has_calls(
            [
                call(amount=Decimal("0.5"), decimal_places=0),
                call(amount=Decimal("0.1"), decimal_places=0),
            ]
        )


@patch.object(supervisor_utils.utils, "one_off_schedule_expression")
class SuperviseeScheduleSyncScheduledEventTest(SupervisorFeatureTest):
    def test_supervisee_schedule_sync_scheduled_event_no_optional_args(
        self, mock_one_off_schedule_expression: MagicMock
    ):
        mock_vault = self.create_supervisor_mock()
        mock_one_off_schedule_expression.return_value = SentinelScheduleExpression(
            "supervisee schedule sync schedule"
        )

        expected = {
            supervisor_utils.SUPERVISEE_SCHEDULE_SYNC_EVENT: ScheduledEvent(
                start_datetime=DEFAULT_DATETIME,
                expression=SentinelScheduleExpression("supervisee schedule sync schedule"),
            )
        }

        result = supervisor_utils.supervisee_schedule_sync_scheduled_event(vault=mock_vault)
        self.assertDictEqual(result, expected)
        mock_one_off_schedule_expression.assert_called_once_with(
            datetime(2019, 1, 1, 0, 0, 30, tzinfo=ZoneInfo(key="UTC"))
        )

    def test_supervisee_schedule_sync_scheduled_event_with_optional_args(
        self, mock_one_off_schedule_expression: MagicMock
    ):
        mock_vault = self.create_supervisor_mock()
        mock_one_off_schedule_expression.return_value = SentinelScheduleExpression(
            "supervisee schedule sync schedule"
        )

        expected = {
            supervisor_utils.SUPERVISEE_SCHEDULE_SYNC_EVENT: ScheduledEvent(
                start_datetime=DEFAULT_DATETIME,
                expression=SentinelScheduleExpression("supervisee schedule sync schedule"),
            )
        }

        result = supervisor_utils.supervisee_schedule_sync_scheduled_event(
            vault=mock_vault, delay_seconds=6
        )
        self.assertDictEqual(result, expected)
        mock_one_off_schedule_expression.assert_called_once_with(
            datetime(2019, 1, 1, 0, 0, 6, tzinfo=ZoneInfo(key="UTC"))
        )


class SuperviseeScheduleSyncEventTypesTest(SupervisorFeatureTest):
    def test_schedule_sync_event_types(self):
        event_types = supervisor_utils.schedule_sync_event_types(product_name="product_a")
        self.assertListEqual(
            event_types,
            [
                SupervisorContractEventType(
                    name=supervisor_utils.SUPERVISEE_SCHEDULE_SYNC_EVENT,
                    scheduler_tag_ids=[
                        f"PRODUCT_A_{supervisor_utils.SUPERVISEE_SCHEDULE_SYNC_EVENT}_AST"
                    ],
                ),
            ],
        )


@patch.object(supervisor_utils, "get_supervisees_for_alias")
@patch.object(supervisor_utils.utils, "one_off_schedule_expression")
class GetSuperviseeScheduleSyncUpdatesTest(SupervisorFeatureTest):
    def test_get_supervisee_schedule_sync_updates_when_supervisees_associated(
        self,
        mock_one_off_schedule_expression: MagicMock,
        mock_get_supervisees_for_alias: MagicMock,
    ):
        mock_get_supervisees_for_alias.return_value = [sentinel.loc_vault]

        def dummy_schedule_updates_when_supervisees(
            loc_vault,
            hook_arguments,
        ):
            return [SentinelUpdateAccountEventTypeDirective("synchronised schedule update")]

        expected_schedule_updates = [
            SentinelUpdateAccountEventTypeDirective("synchronised schedule update")
        ]
        schedule_updates = supervisor_utils.get_supervisee_schedule_sync_updates(
            vault=sentinel.vault,
            supervisee_alias=sentinel.supervisee_alias,
            hook_arguments=sentinel.hook_arguments,
            schedule_updates_when_supervisees=dummy_schedule_updates_when_supervisees,  # type: ignore # noqa: E501
        )
        self.assertEqual(expected_schedule_updates, schedule_updates)
        mock_get_supervisees_for_alias.assert_called_once_with(
            vault=sentinel.vault, alias=sentinel.supervisee_alias
        )
        mock_one_off_schedule_expression.assert_not_called()

    def test_get_supervisee_schedule_sync_updates_when_no_supervisees(
        self,
        mock_one_off_schedule_expression: MagicMock,
        mock_get_supervisees_for_alias: MagicMock,
    ):
        mock_get_supervisees_for_alias.return_value = []
        mock_one_off_schedule_expression.return_value = SentinelScheduleExpression("reschedule")

        expected_schedule_updates = [
            UpdatePlanEventTypeDirective(
                event_type=supervisor_utils.SUPERVISEE_SCHEDULE_SYNC_EVENT,
                expression=SentinelScheduleExpression("reschedule"),
            )
        ]
        schedule_updates = supervisor_utils.get_supervisee_schedule_sync_updates(
            vault=sentinel.vault,
            supervisee_alias=sentinel.supervisee_alias,
            hook_arguments=SupervisorScheduledEventHookArguments(
                effective_datetime=DEFAULT_DATETIME,
                event_type=sentinel.event_type,
                supervisee_pause_at_datetime={},
            ),
            schedule_updates_when_supervisees=lambda _: _,  # type: ignore
            delay_seconds=10,
        )
        self.assertEqual(expected_schedule_updates, schedule_updates)
        mock_get_supervisees_for_alias.assert_called_once_with(
            vault=sentinel.vault, alias=sentinel.supervisee_alias
        )
        mock_one_off_schedule_expression.assert_called_once_with(
            schedule_datetime=DEFAULT_DATETIME + relativedelta(seconds=10)
        )
