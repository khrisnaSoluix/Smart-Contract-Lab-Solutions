# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Optional
from unittest.mock import ANY, MagicMock, call, patch, sentinel
from zoneinfo import ZoneInfo

# library
from library.credit_card.contracts.template import credit_card
from library.credit_card.test.unit.test_credit_card_common import CreditCardTestBase

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Balance,
    BalancesObservation,
    CustomInstruction,
    Phase,
    Posting,
)

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DATETIME,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    AccountNotificationDirective,
    BalanceCoordinate,
    BalanceDefaultDict,
    ClientTransaction,
    PostingInstructionsDirective,
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    DEFAULT_POSTINGS,
    SentinelAccountNotificationDirective,
    SentinelBalance,
    SentinelBalancesObservation,
    SentinelCustomInstruction,
)

DEFAULT_COORDINATE = BalanceCoordinate(DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.COMMITTED)


class UpdateBalancesTest(CreditCardTestBase):
    def test_update_balances_with_multiple_coordinates_affected(self):
        # construct mocks
        mock_vault = self.create_mock()
        balances = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(
                    account_address="TEST_ADDRESS", denomination="XAU"
                ): self.balance(debit=Decimal("100"), credit=Decimal("0"))
            }
        )
        posting_instructions = [
            CustomInstruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("200"),
                        denomination="XAU",
                        account_id=ACCOUNT_ID,
                        account_address="TEST_ADDRESS",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("200"),
                        denomination="XAU",
                        account_id="DIFFERENT_ACCOUNT",
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ]
            ),
            CustomInstruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("200"),
                        denomination="ZZZ",
                        account_id=ACCOUNT_ID,
                        account_address="NEW_ADDRESS",
                        asset="1234",
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("200"),
                        denomination="ZZZ",
                        account_id="DIFFERENT_ACCOUNT",
                        account_address=DEFAULT_ADDRESS,
                        asset="1234",
                        phase=Phase.COMMITTED,
                    ),
                ]
            ),
        ]

        # construct expected result
        expected_balances = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(
                    account_address="TEST_ADDRESS", denomination="XAU"
                ): self.balance(
                    credit=Decimal("200"),
                    debit=Decimal("100"),
                ),
                self.balance_coordinate(
                    account_address="NEW_ADDRESS", denomination="ZZZ", asset="1234"
                ): self.balance(
                    debit=Decimal("0"),
                    credit=Decimal("200"),
                ),
            }
        )
        # run function
        credit_card._update_balances(
            account_id=mock_vault.account_id,
            balances=balances,
            posting_instructions=posting_instructions,
        )
        self.assertDictEqual(balances, expected_balances)


class AccrueInterestTest(CreditCardTestBase):
    def setUp(self) -> None:
        # do all mocks, patches, etc
        self.common_get_param_return_values: dict = {
            "accrue_interest_on_unpaid_interest": "False",
            "accrue_interest_on_unpaid_fees": "False",
            "accrue_interest_from_txn_day": "True",
            "base_interest_rates": {
                "purchase": "0.01",
                "cash_advance": "0.02",
                "transfer": "0.03",
                "fees": "0.01",
            },
            "transaction_base_interest_rates": {
                "balance_transfer": {"REF1": "0.022", "REF2": "0.035"}
            },
            "payment_due_period": "21",
        }

        patch_get_parameter = patch.object(credit_card.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values},
        )

        patch_get_balances_to_accrue_on = patch.object(credit_card, "_get_balances_to_accrue_on")
        self.mock_get_balances_to_accrue_on = patch_get_balances_to_accrue_on.start()

        effective_datetime = datetime(2020, 4, 5, 6, 7, 8, 9, tzinfo=ZoneInfo("UTC"))
        self.accrual_cut_off_datetime = effective_datetime.replace(
            hour=0, minute=0, second=0
        ) - relativedelta(microseconds=1)

        self.balances = BalanceDefaultDict(
            mapping={
                DEFAULT_COORDINATE: SentinelBalance(""),
            }
        )

        self.instructions = [CustomInstruction(postings=DEFAULT_POSTINGS)]
        self.supported_txn_types: dict = {}
        self.supported_fee_types: list = []
        self.txn_types_to_charge_interest_from_txn_date: list = []
        self.txn_types_in_interest_free_period = {
            "cash_advance": [],
            "purchase": [],
            "balance_transfer": ["REF1"],
        }
        self.is_revolver = True

        # construct mocks
        self.mock_vault = self.create_mock()

        patch_is_between_pdd_and_scod = patch.object(credit_card, "_is_between_pdd_and_scod")
        self.mock_is_between_pdd_and_scod = patch_is_between_pdd_and_scod.start()

        patch_determine_txns_currently_interest_free = patch.object(
            credit_card, "_determine_txns_currently_interest_free"
        )
        self.mock_determine_txns_currently_interest_free = (
            patch_determine_txns_currently_interest_free.start()
        )
        self.mock_determine_txns_currently_interest_free.return_value = (
            "base_interest_rates",
            "txn_base_interest_rates",
        )

        patch_combine_txn_and_type_rates = patch.object(credit_card, "_combine_txn_and_type_rates")
        self.mock_combine_txn_and_type_rates = patch_combine_txn_and_type_rates.start()

        patch_isleap = patch.object(credit_card.utils, "isleap")
        self.mock_isleap = patch_isleap.start()

        patch_calculate_accruals_and_create_instructions = patch.object(
            credit_card, "_calculate_accruals_and_create_instructions"
        )
        self.mock_calculate_accruals_and_create_instructions = (
            patch_calculate_accruals_and_create_instructions.start()
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_accrue_interest_no_balances_to_accrue_on(self):
        balances_to_accrue_on = {}
        self.mock_get_balances_to_accrue_on.return_value = balances_to_accrue_on

        # construct expected result
        expected_result = {}

        # run hook
        result = credit_card._accrue_interest(
            self.mock_vault,
            self.accrual_cut_off_datetime,
            "GBP",
            self.balances,
            self.instructions,
            self.supported_txn_types,
            self.supported_fee_types,
            self.txn_types_to_charge_interest_from_txn_date,
            self.txn_types_in_interest_free_period,
            self.is_revolver,
        )

        # validate result
        self.assertDictEqual(result, expected_result)

    def test_accrue_interest_balances_to_accrue_on_is_between_pdd_and_scod(self):
        balances_to_accrue_on = {
            ("PRINCIPAL", "balance_transfer", ""): {"REF1": 1.23, "REF2": 4.56}
        }
        self.mock_get_balances_to_accrue_on.return_value = balances_to_accrue_on

        self.mock_is_between_pdd_and_scod.return_value = True

        self.mock_combine_txn_and_type_rates.return_value = "txn_and_type_rates"
        self.mock_isleap = sentinel.bool
        self.mock_calculate_accruals_and_create_instructions.return_value = {
            ("PRINCIPAL", "balance_transfer", ""): {"REF1": 1.23, "REF2": 4.56}
        }
        expected_result = {("PRINCIPAL", "balance_transfer", ""): {"REF1": 1.23, "REF2": 4.56}}

        # run hook
        result = credit_card._accrue_interest(
            self.mock_vault,
            self.accrual_cut_off_datetime,
            "GBP",
            self.balances,
            self.instructions,
            self.supported_txn_types,
            self.supported_fee_types,
            self.txn_types_to_charge_interest_from_txn_date,
            self.txn_types_in_interest_free_period,
            self.is_revolver,
        )

        # validate result
        self.assertDictEqual(result, expected_result)


@patch.object(credit_card, "_rebalance_balance_buckets")
@patch.object(credit_card, "_interest_address")
class AdjustInterestUnchargedBalancesTest(CreditCardTestBase):
    def test_adjust_interest_uncharged_balances(
        self,
        mock_interest_address: MagicMock,
        mock_rebalance_balance_buckets: MagicMock,
    ):
        # construct values
        rebalance_postings = [SentinelCustomInstruction("rebalance_postings")]
        supported_txn_types: dict[str, Optional[list[str]]] = {
            "PURCHASE": [sentinel.txn_ref],
            "CASH_ADVANCE": None,
            "BALANCE_TRANSFER": None,
        }
        txn_types_to_charge_interest_from_txn_date = [
            "cash_advance",
            "balance_transfer",
        ]

        # construct mocks
        mock_vault = self.create_mock()
        mock_interest_address.side_effect = [
            sentinel.from_balance_address,
            sentinel.to_balance_address,
        ]
        mock_rebalance_balance_buckets.return_value = (
            sentinel._,
            rebalance_postings,
        )

        # run function
        result = credit_card._adjust_interest_uncharged_balances(
            vault=mock_vault,
            supported_txn_types=supported_txn_types,
            txn_types_to_charge_interest_from_txn_date=txn_types_to_charge_interest_from_txn_date,
            denomination=self.default_denomination,
            in_flight_balances=sentinel.in_flight_balances,
        )
        self.assertEqual(rebalance_postings, result)

        # assert calls
        mock_interest_address.assert_has_calls(
            calls=[
                call(
                    "PURCHASE",
                    "UNCHARGED",
                    txn_ref=sentinel.txn_ref,
                    accrual_type="PRE_SCOD",
                ),
                call(
                    "PURCHASE",
                    "UNCHARGED",
                    txn_ref=sentinel.txn_ref,
                    accrual_type="POST_SCOD",
                ),
            ]
        )
        mock_rebalance_balance_buckets.assert_called_once_with(
            mock_vault,
            sentinel.in_flight_balances,
            sentinel.from_balance_address,
            sentinel.to_balance_address,
            self.default_denomination,
        )


class YearlyToDailyRateTest(CreditCardTestBase):
    def test_yearly_to_daily_rate_in_leap_year(self):
        daily_rate = credit_card.yearly_to_daily_rate(yearly_rate=Decimal("0.1"), leap_year=True)
        self.assertEqual(daily_rate, Decimal("0.0002732240"))

    def test_yearly_to_daily_rate_in_non_leap_year(self):
        daily_rate = credit_card.yearly_to_daily_rate(yearly_rate=Decimal("0.1"), leap_year=False)
        self.assertEqual(daily_rate, Decimal("0.0002739726"))


class GetDenominationFromPostingInstructionTest(CreditCardTestBase):
    def test_get_custom_instruction_denomination(self):
        custom_instruction = SentinelCustomInstruction("ci")
        # postings are DEFAULT_POSTINGS
        expected_result = sentinel.denomination
        result = credit_card.get_denomination_from_posting_instruction(
            posting_instruction=custom_instruction
        )
        self.assertEqual(result, expected_result)

    def test_get_inbound_authorisation_denomination(self):
        custom_instruction = self.inbound_auth(amount=Decimal("1"), denomination="GBP")
        expected_result = "GBP"
        result = credit_card.get_denomination_from_posting_instruction(
            posting_instruction=custom_instruction
        )
        self.assertEqual(result, expected_result)


class AgeOverdueAddressTest(CreditCardTestBase):
    @patch.object(credit_card, "_get_overdue_address_age")
    def test_age_overdue_address(
        self,
        mock_get_overdue_address_age: MagicMock,
    ):
        # construct mocks
        mock_get_overdue_address_age.return_value = 1

        # run function
        result = credit_card._age_overdue_address(overdue_address="OVERDUE_1")
        self.assertEqual("OVERDUE_2", result)

        # assert calls
        mock_get_overdue_address_age.assert_called_once_with("OVERDUE_1")


class GetOverdueAddressAgeTest(CreditCardTestBase):
    def test_age_overdue_address(self):
        # construct values
        expected_age = 123

        # run function
        result = credit_card._get_overdue_address_age(overdue_address=f"OVERDUE_{expected_age}")
        self.assertEqual(expected_age, result)


class ChargeInterestTest(CreditCardTestBase):
    def setUp(self):
        self.mock_vault = sentinel.vault
        self.is_revolver = True
        self.accruals_by_sub_type = {("PRINCIPAL", "CASH_ADVANCE", ""): {"": Decimal("5.92")}}
        self.txn_types_to_charge_interest_from_txn_date = []
        self.in_flight_balances = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(
                    account_address="TEST_ADDRESS", denomination=self.default_denomination
                ): self.balance(
                    credit=Decimal("200"),
                    debit=Decimal("100"),
                ),
            }
        )
        self.instructions = [SentinelCustomInstruction("charge_interest_id")]
        self.txn_types_in_interest_free_period = {}
        self.is_pdd = False
        self.charge_interest_free_period = False

        patch_make_accrual_posting = patch.object(credit_card, "_make_accrual_posting")
        self.mock_make_accrual_posting = patch_make_accrual_posting.start()

        patch_rebalance_interest = patch.object(credit_card, "_rebalance_interest")
        self.mock_rebalance_interest = patch_rebalance_interest.start()

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_charge_interest_is_revolver_not_pdd(self):
        is_pdd = False

        # run function
        credit_card._charge_interest(
            self.mock_vault,
            self.is_revolver,
            self.default_denomination,
            self.accruals_by_sub_type,
            self.txn_types_to_charge_interest_from_txn_date,
            self.in_flight_balances,
            self.instructions,
            self.txn_types_in_interest_free_period,
            is_pdd,
            self.charge_interest_free_period,
        )

        self.mock_make_accrual_posting.assert_not_called()
        self.mock_rebalance_interest.assert_called_once_with(
            vault=self.mock_vault,
            amount=Decimal("5.92"),
            denomination=self.default_denomination,
            in_flight_balances=self.in_flight_balances,
            charge_type="PRINCIPAL",
            sub_type="CASH_ADVANCE",
            instructions=self.instructions,
            txn_ref="",
        )

    def test_charge_interest_is_not_revolver(self):
        is_revolver = False
        is_pdd = False

        # run function
        credit_card._charge_interest(
            self.mock_vault,
            is_revolver,
            self.default_denomination,
            self.accruals_by_sub_type,
            self.txn_types_to_charge_interest_from_txn_date,
            self.in_flight_balances,
            self.instructions,
            self.txn_types_in_interest_free_period,
            is_pdd,
            self.charge_interest_free_period,
        )

        self.mock_make_accrual_posting.assert_not_called()
        self.mock_rebalance_interest.assert_not_called()

    def test_charge_interest_is_revolver_txn_charge_amount_0(self):
        is_pdd = False
        accruals_by_sub_type = {("PRINCIPAL", "CASH_ADVANCE", ""): {"": Decimal("0")}}

        # run function
        credit_card._charge_interest(
            self.mock_vault,
            self.is_revolver,
            self.default_denomination,
            accruals_by_sub_type,
            self.txn_types_to_charge_interest_from_txn_date,
            self.in_flight_balances,
            self.instructions,
            self.txn_types_in_interest_free_period,
            is_pdd,
            self.charge_interest_free_period,
        )

        self.mock_make_accrual_posting.assert_not_called()
        self.mock_rebalance_interest.assert_not_called()

    def test_charge_interest_is_revolver_is_pdd_is_not_charge_interest_free_period(self):
        is_pdd = True

        # run function
        credit_card._charge_interest(
            self.mock_vault,
            self.is_revolver,
            self.default_denomination,
            self.accruals_by_sub_type,
            self.txn_types_to_charge_interest_from_txn_date,
            self.in_flight_balances,
            self.instructions,
            self.txn_types_in_interest_free_period,
            is_pdd,
            self.charge_interest_free_period,
        )

        self.mock_make_accrual_posting.assert_called_once_with(
            self.mock_vault,
            accrual_amount=Decimal("5.92"),
            denomination=self.default_denomination,
            stem="CASH_ADVANCE",
            reverse=True,
            instruction_details={
                "description": "Uncharged interest reversed for CASH_ADVANCE - INTEREST_CHARGED"
            },
            accrual_type="",
        )
        self.mock_rebalance_interest.assert_called_once_with(
            vault=self.mock_vault,
            amount=Decimal("5.92"),
            denomination=self.default_denomination,
            in_flight_balances=self.in_flight_balances,
            charge_type="PRINCIPAL",
            sub_type="CASH_ADVANCE",
            instructions=self.instructions,
            txn_ref="",
        )

    def test_charge_interest_is_revolver_is_pdd_is_charge_interest_free_period(self):
        is_pdd = True
        charge_interest_free_period = True

        # run function
        credit_card._charge_interest(
            self.mock_vault,
            self.is_revolver,
            self.default_denomination,
            self.accruals_by_sub_type,
            self.txn_types_to_charge_interest_from_txn_date,
            self.in_flight_balances,
            self.instructions,
            self.txn_types_in_interest_free_period,
            is_pdd,
            charge_interest_free_period,
        )

        self.mock_make_accrual_posting.assert_not_called
        self.mock_rebalance_interest.assert_called_once_with(
            vault=self.mock_vault,
            amount=Decimal("5.92"),
            denomination=self.default_denomination,
            in_flight_balances=self.in_flight_balances,
            charge_type="PRINCIPAL",
            sub_type="CASH_ADVANCE",
            instructions=self.instructions,
            txn_ref="",
        )

    def test_charge_interest_is_revolver_is_pdd_accrual_type(self):
        is_pdd = True
        accruals_by_sub_type = {("PRINCIPAL", "CASH_ADVANCE", "TEST"): {"": Decimal("100")}}

        # run function
        credit_card._charge_interest(
            self.mock_vault,
            self.is_revolver,
            self.default_denomination,
            accruals_by_sub_type,
            self.txn_types_to_charge_interest_from_txn_date,
            self.in_flight_balances,
            self.instructions,
            self.txn_types_in_interest_free_period,
            is_pdd,
            self.charge_interest_free_period,
        )

        self.mock_make_accrual_posting.assert_called_once_with(
            self.mock_vault,
            accrual_amount=Decimal("100"),
            denomination=self.default_denomination,
            stem="CASH_ADVANCE",
            reverse=True,
            instruction_details={
                "description": "Uncharged interest reversed for CASH_ADVANCE_TEST - "
                "INTEREST_CHARGED"
            },
            accrual_type="TEST",
        )
        self.mock_rebalance_interest.assert_called_once_with(
            vault=self.mock_vault,
            amount=Decimal("100"),
            denomination=self.default_denomination,
            in_flight_balances=self.in_flight_balances,
            charge_type="PRINCIPAL",
            sub_type="CASH_ADVANCE",
            instructions=self.instructions,
            txn_ref="",
        )


@patch.object(credit_card, "_adjust_aggregate_balances")
@patch.object(credit_card, "_charge_fee")
@patch.object(credit_card, "_deep_copy_balances")
@patch.object(credit_card.utils, "get_parameter")
class ChargeAnnualFeeTest(CreditCardTestBase):
    def test_non_zero_annual_fee_and_pi_directive_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_deep_copy_balances: MagicMock,
        mock_charge_fee: MagicMock,
        mock_adjust_aggregate_balances: MagicMock,
    ):
        # Construct mocks
        live_balances_observation = SentinelBalancesObservation("live_balances")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                credit_card.LIVE_BALANCES_BOF_ID: (live_balances_observation),
            }
        )

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "credit_limit": sentinel.credit_limit,
                "annual_fee": sentinel.annual_fee,
            }
        )
        mock_deep_copy_balances.return_value = SentinelBalancesObservation("deep_copy")
        mock_charge_fee.return_value = [
            sentinel.annual_fee,
            [SentinelCustomInstruction("charge_fee")],
        ]
        mock_adjust_aggregate_balances.return_value = [
            SentinelCustomInstruction("adjust_aggregate_balances")
        ]
        # Expected results
        expected_result = [
            PostingInstructionsDirective(
                posting_instructions=[
                    SentinelCustomInstruction("charge_fee"),
                    SentinelCustomInstruction("adjust_aggregate_balances"),
                ],
                client_batch_id=f"{credit_card.ANNUAL_FEE}-{mock_vault.get_hook_execution_id()}",
                value_datetime=DEFAULT_DATETIME,
            ),
        ]
        # Run
        result = credit_card._charge_annual_fee(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )

        # Assert
        self.assertEqual(result, expected_result)

    def test_zero_annual_fee_and_no_pi_directive_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_deep_copy_balances: MagicMock,
        mock_charge_fee: MagicMock,
        mock_adjust_aggregate_balances: MagicMock,
    ):
        # Construct mocks
        live_balances_observation = SentinelBalancesObservation("live_balances")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                credit_card.LIVE_BALANCES_BOF_ID: (live_balances_observation),
            }
        )

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "credit_limit": sentinel.credit_limit,
                "annual_fee": Decimal("0"),
            }
        )
        mock_deep_copy_balances.return_value = SentinelBalancesObservation("deep_copy")
        mock_charge_fee.return_value = [
            Decimal("0"),
            [],
        ]

        # Run
        result = credit_card._charge_annual_fee(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )

        # Assert
        self.assertEqual(result, [])
        mock_charge_fee.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            in_flight_balances=SentinelBalancesObservation("deep_copy"),
            fee_type=credit_card.ANNUAL_FEE,
        )
        mock_adjust_aggregate_balances.assert_not_called()

    def test_negative_annual_fee_no_pi_directive_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_deep_copy_balances: MagicMock,
        mock_charge_fee: MagicMock,
        mock_adjust_aggregate_balances: MagicMock,
    ):
        # TODO Does it make sense to allow negative fee amount?
        # For a non-zero annual fee, the only way to end with no posting instruction directive
        # returned is for the annual fee to be negative.
        # Construct mocks
        live_balances_observation = SentinelBalancesObservation("live_balances")
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                credit_card.LIVE_BALANCES_BOF_ID: (live_balances_observation),
            }
        )

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "credit_limit": sentinel.credit_limit,
                "annual_fee": Decimal("-100"),
            }
        )
        mock_deep_copy_balances.return_value = SentinelBalancesObservation("deep_copy")
        mock_charge_fee.return_value = [
            Decimal("-100"),
            [],
        ]
        mock_adjust_aggregate_balances.return_value = []

        # Run
        result = credit_card._charge_annual_fee(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )

        # Assert
        self.assertEqual(result, [])
        mock_charge_fee.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            in_flight_balances=SentinelBalancesObservation("deep_copy"),
            fee_type=credit_card.ANNUAL_FEE,
        )
        mock_adjust_aggregate_balances.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            SentinelBalancesObservation("deep_copy"),
            DEFAULT_DATETIME,
            credit_limit=sentinel.credit_limit,
        )


class GetSupportedTxnTypesTest(CreditCardTestBase):
    @patch.object(credit_card.utils, "get_parameter")
    def test_mapping_of_txn_type_to_txn_ref_returned(
        self,
        mock_get_parameter: MagicMock,
    ):
        txn_types_params: dict = {
            credit_card.PARAM_TXN_TYPES: {
                "balance_transfer": {"charge_interest_from_transaction_date": "True"}
            },
        }
        txn_ref_params: dict = {credit_card.PARAM_TXN_REFS: {"balance_transfer": ["REF1", "REF2"]}}
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**txn_types_params, **txn_ref_params}
        )

        expected_result = {"BALANCE_TRANSFER": ["REF1", "REF2"]}

        result = credit_card._get_supported_txn_types(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_datetime,
        )

        self.assertEqual(result, expected_result)


@patch.object(credit_card, "_rebalance_fees")
@patch.object(credit_card, "_get_fee_internal_account")
@patch.object(credit_card.utils, "get_parameter")
class ChargeFeeTest(CreditCardTestBase):
    def test_positive_fee_amount_and_ci_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_get_fee_internal_account: MagicMock,
        mock_rebalance_fees: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={sentinel.fee_type: sentinel.fee_amount}
        )
        mock_get_fee_internal_account.return_value = sentinel.internal_account
        mock_rebalance_fees.return_value = [SentinelCustomInstruction("rebalance_fees")]

        expected_result = (sentinel.fee_amount, [SentinelCustomInstruction("rebalance_fees")])

        result = credit_card._charge_fee(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            fee_type=sentinel.fee_type,
            fee_amount=sentinel.fee_amount,
            is_external_fee=sentinel.is_external_fee,
        )

        self.assertEqual(result, expected_result)
        mock_rebalance_fees.assert_called_once_with(
            sentinel.vault,
            sentinel.fee_amount,
            sentinel.denomination,
            sentinel.in_flight_balances,
            sentinel.internal_account,
            sentinel.fee_type,
        )

    def test_zero_fee_amount_and_no_ci_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_get_fee_internal_account: MagicMock,
        mock_rebalance_fees: MagicMock,
    ):
        fee_amount = Decimal("0")

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"sentinel_fee_type": fee_amount}
        )

        expected_result: tuple[Decimal, list[CustomInstruction]] = (Decimal("0"), [])

        result = credit_card._charge_fee(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            fee_type="SENTINEL_FEE_TYPE",
            fee_amount=Decimal(fee_amount),
            is_external_fee=False,
        )

        self.assertEqual(result, expected_result)
        mock_get_fee_internal_account.assert_not_called()
        mock_rebalance_fees.assert_not_called()

    def test_negative_fee_amount_and_no_ci_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_get_fee_internal_account: MagicMock,
        mock_rebalance_fees: MagicMock,
    ):
        # TODO - Does it make sense to accept a negative fee_amount?
        fee_amount = Decimal("-100")
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"sentinel.fee_type": fee_amount}
        )

        mock_get_fee_internal_account.return_value = sentinel.internal_account
        mock_rebalance_fees.return_value = []

        expected_result: tuple[Decimal, list[CustomInstruction]] = (fee_amount, [])

        result = credit_card._charge_fee(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            fee_type="sentinel.fee_type",
            fee_amount=fee_amount,
            is_external_fee=False,
        )

        self.assertEqual(result, expected_result)
        mock_get_fee_internal_account.assert_called_once_with(
            sentinel.vault,
            "sentinel.fee_type",
            "",
            False,
        )
        mock_rebalance_fees.assert_called_once_with(
            sentinel.vault,
            fee_amount,
            sentinel.denomination,
            sentinel.in_flight_balances,
            sentinel.internal_account,
            "sentinel.fee_type",
        )


@patch.object(credit_card, "_change_revolver_status")
@patch.object(credit_card.utils, "balance_at_coordinates")
@patch.object(credit_card, "_override_info_balance")
@patch.object(credit_card, "_calculate_aggregate_balance")
@patch.object(credit_card, "_get_supported_fee_types")
@patch.object(credit_card, "_get_supported_txn_types")
class AdjustAggregateBalancesTest(CreditCardTestBase):
    def test_adjust_inscope_balances_and_cis_returned(
        self,
        mock_get_supported_txn_types: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_calculate_aggregate_balance: MagicMock,
        mock_override_info_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_change_revolver_status: MagicMock,
    ):
        # Construct mock
        mock_get_supported_txn_types.return_value = [sentinel.supported_txn_types]
        mock_get_supported_fee_types.return_value = [sentinel.supported_fee_types]
        mock_calculate_aggregate_balance.return_value = Decimal("0")
        mock_override_info_balance.side_effect = [
            [SentinelCustomInstruction("override_info_balance_AVAILABLE")],
            [SentinelCustomInstruction("override_info_balance_OUTSTANDING")],
            [SentinelCustomInstruction("override_info_balance_FULL_OUTSTANDING")],
        ]
        mock_balance_at_coordinates.return_value = Decimal("0")
        mock_change_revolver_status.return_value = [
            SentinelCustomInstruction("change_revolver_status")
        ]

        # Expected results
        expected_result = [
            SentinelCustomInstruction("override_info_balance_AVAILABLE"),
            SentinelCustomInstruction("override_info_balance_OUTSTANDING"),
            SentinelCustomInstruction("override_info_balance_FULL_OUTSTANDING"),
            SentinelCustomInstruction("change_revolver_status"),
        ]

        purchase_charged_balance = Balance(net=Decimal("75"))
        available_balance = Balance(net=Decimal("925"))
        outstanding_balance = Balance(net=Decimal("75"))
        full_outstanding_balance = Balance(net=Decimal("75"))

        PURCHASE_CHARGED_COORDINATE = BalanceCoordinate(
            account_address="PURCHASE_CHARGED",
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )
        AVAILABLE_COORDINATE_COORDINATE = BalanceCoordinate(
            account_address="AVAILABLE_BALANCE",
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )
        OUTSTANDING_COORDINATE = BalanceCoordinate(
            account_address="OUTSTANDING_BALANCE",
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )
        FULL_OUTSTANDING_COORDINATE = BalanceCoordinate(
            account_address="FULL_OUTSTANDING_BALANCE",
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.COMMITTED,
        )

        in_flight_balances = BalanceDefaultDict(
            None,
            {
                PURCHASE_CHARGED_COORDINATE: purchase_charged_balance,
                AVAILABLE_COORDINATE_COORDINATE: available_balance,
                OUTSTANDING_COORDINATE: outstanding_balance,
                FULL_OUTSTANDING_COORDINATE: full_outstanding_balance,
            },
        )

        # Run
        result = credit_card._adjust_aggregate_balances(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            in_flight_balances=in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
            available=sentinel.available,
            outstanding=sentinel.outstanding,
            full_outstanding=sentinel.full_outstanding,
        )

        # Assert
        self.assertEqual(result, expected_result)

    def test_adjust_not_inscope_balances_and_no_cis_returned(
        self,
        mock_get_supported_txn_types: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_calculate_aggregate_balance: MagicMock,
        mock_override_info_balance: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_change_revolver_status: MagicMock,
    ):
        # Construct mock
        mock_get_supported_txn_types.return_value = [sentinel.supported_txn_types]
        mock_get_supported_fee_types.return_value = [sentinel.supported_fee_types]
        mock_balance_at_coordinates.return_value = Decimal("0")
        mock_change_revolver_status.return_value = [
            SentinelCustomInstruction("change_revolver_status")
        ]

        # Run
        result = credit_card._adjust_aggregate_balances(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
            available=False,
            outstanding=False,
            full_outstanding=False,
        )

        # Assert
        self.assertEqual(result, [])
        mock_calculate_aggregate_balance.assert_not_called()
        mock_override_info_balance.assert_not_called()


class GetSupportedFeeTypesTest(CreditCardTestBase):
    @patch.object(credit_card, "_get_supported_txn_types")
    @patch.object(credit_card.utils, "get_parameter")
    def test_supported_fees_that_can_be_charged_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_get_supported_txn_types: MagicMock,
    ):
        fee_types_params: dict = {
            credit_card.PARAM_EXTERNAL_FEE_TYPES: ["DISPUTE_FEE", "ATM_WITHDRAWAL_FEE"]
        }
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**fee_types_params},
        )

        mock_get_supported_txn_types.return_value = {
            "BALANCE_TRANSFER": ["charge_interest_from_transaction_date"]
        }

        expected_result = sorted(
            credit_card.INTERNAL_FEE_TYPES.copy()
            + ["DISPUTE_FEE", "ATM_WITHDRAWAL_FEE"]
            + ["BALANCE_TRANSFER_FEE"]
        )

        result = credit_card._get_supported_fee_types(
            vault=sentinel.vault,
        )

        self.assertEqual(result, expected_result)


@patch.object(credit_card, "_make_internal_address_transfer")
@patch.object(credit_card.utils, "balance_at_coordinates")
class OverrideInfoBalanceTest(CreditCardTestBase):
    def test_set_balance_to_new_amount_eq_to_balance_and_no_ci_returned(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        mock_balance_at_coordinates.return_value = Decimal("100")

        result = credit_card._override_info_balance(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            balance_address=sentinel.balance_address,
            denomination=sentinel.denomination,
            amount=Decimal("100"),
        )

        self.assertEqual(result, [])
        mock_make_internal_address_transfer.assert_not_called()

    def test_set_balance_to_new_amount_gt_balance_and_ci_returned(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        mock_balance_at_coordinates.return_value = Decimal("100")
        mock_make_internal_address_transfer.return_value = SentinelCustomInstruction(
            "credit_internal_True"
        )

        expected_result = SentinelCustomInstruction("credit_internal_True")

        result = credit_card._override_info_balance(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            balance_address=sentinel.balance_address,
            denomination=sentinel.denomination,
            amount=Decimal("200"),
        )

        self.assertEqual(result, expected_result)
        mock_make_internal_address_transfer.assert_called_once_with(
            custom_address=sentinel.balance_address,
            credit_internal=True,
            denomination=sentinel.denomination,
            amount=Decimal("100"),
            instruction_details={"description": "Set sentinel.balance_address to 200.00"},
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
        )

    def test_set_balance_to_new_amount_lt_balance_and_ci_returned(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        mock_balance_at_coordinates.return_value = Decimal("100")
        mock_make_internal_address_transfer.return_value = SentinelCustomInstruction(
            "credit_internal_True"
        )

        expected_result = SentinelCustomInstruction("credit_internal_True")

        result = credit_card._override_info_balance(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            balance_address=sentinel.balance_address,
            denomination=sentinel.denomination,
            amount=Decimal("80"),
        )

        self.assertEqual(result, expected_result)
        mock_make_internal_address_transfer.assert_called_once_with(
            custom_address=sentinel.balance_address,
            credit_internal=False,
            denomination=sentinel.denomination,
            amount=Decimal("20"),
            instruction_details={"description": "Set sentinel.balance_address to 80.00"},
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
        )


@patch.object(credit_card, "_make_internal_address_transfer")
@patch.object(credit_card, "_is_revolver")
class ChangeRevolverStatusTest(CreditCardTestBase):
    def test_set_revolver_to_same_status_as_current_is_revolver_and_no_ci_returned(
        self,
        mock_is_revolver: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        mock_is_revolver.return_value = sentinel.revolver_status

        result = credit_card._change_revolver_status(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            revolver=sentinel.revolver_status,
        )

        self.assertEqual(result, [])
        mock_make_internal_address_transfer.assert_not_called()

    def test_set_revolver_true_when_already_is_not_revolver_and_ci_returned(
        self,
        mock_is_revolver: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        mock_is_revolver.return_value = False
        mock_make_internal_address_transfer.return_value = SentinelCustomInstruction(
            "set_revolver_status"
        )

        expected_result = SentinelCustomInstruction("set_revolver_status")

        result = credit_card._change_revolver_status(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            revolver=True,
        )
        self.assertEqual(result, expected_result)

    def test_unset_revolver_when_is_revolver_and_ci_returned(
        self,
        mock_is_revolver: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        mock_is_revolver.return_value = True
        mock_make_internal_address_transfer.return_value = SentinelCustomInstruction(
            "unset_revolver_status"
        )

        expected_result = SentinelCustomInstruction("unset_revolver_status")

        result = credit_card._change_revolver_status(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            revolver=False,
        )
        self.assertEqual(result, expected_result)


class IsRevolverTest(CreditCardTestBase):
    def test_is_revolver_true(self):
        revolver_balance = Balance(net=Decimal("1"))
        REVOLVER_BALANCE_COORDINATE = BalanceCoordinate(
            account_address=credit_card.REVOLVER_BALANCE,
            asset=DEFAULT_ASSET,
            denomination=sentinel.denomination,
            phase=Phase.COMMITTED,
        )
        test_balances = BalanceDefaultDict(None, {REVOLVER_BALANCE_COORDINATE: revolver_balance})

        result = credit_card._is_revolver(
            balances=test_balances,
            denomination=sentinel.denomination,
        )

        self.assertTrue(result)

    def test_is_revolver_false(self):
        revolver_balance = Balance(net=Decimal("0"))
        REVOLVER_BALANCE_COORDINATE = BalanceCoordinate(
            account_address=credit_card.REVOLVER_BALANCE,
            asset=DEFAULT_ASSET,
            denomination=sentinel.denomination,
            phase=Phase.COMMITTED,
        )
        test_balances = BalanceDefaultDict(None, {REVOLVER_BALANCE_COORDINATE: revolver_balance})

        result = credit_card._is_revolver(
            balances=test_balances,
            denomination=sentinel.denomination,
        )

        self.assertFalse(result)


@patch.object(credit_card, "_make_deposit_postings")
@patch.object(credit_card, "_make_internal_address_transfer")
@patch.object(credit_card, "_fee_address")
@patch.object(credit_card, "_create_custom_instructions")
@patch.object(credit_card, "_determine_amount_breakdown")
@patch.object(credit_card, "_get_supported_fee_types")
@patch.object(credit_card.utils, "get_parameter")
@patch.object(credit_card.utils, "round_decimal")
class RebalanceFeesTest(CreditCardTestBase):
    def test_zero_fee_amount_and_no_ci_returned(
        self,
        mock_round_decimal: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_determine_amount_breakdown: MagicMock,
        mock_create_custom_instructions: MagicMock,
        mock_fee_address: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
        mock_make_deposit_postings: MagicMock,
    ):
        mock_round_decimal.return_value = Decimal("0.00")

        result = credit_card._rebalance_fees(
            vault=sentinel.vault,
            amount=Decimal("0"),
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            income_account=sentinel.income_account,
            fee_type=sentinel.fee_type,
        )

        self.assertEqual(result, [])
        mock_get_parameter.assert_not_called()
        mock_get_supported_fee_types.assert_not_called()
        mock_determine_amount_breakdown.assert_not_called()
        mock_create_custom_instructions.assert_not_called()
        mock_fee_address.assert_not_called()
        mock_make_internal_address_transfer.assert_not_called()
        mock_make_deposit_postings.assert_not_called()

    def test_negative_fee_amount_and_no_ci_returned(
        self,
        mock_round_decimal: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_determine_amount_breakdown: MagicMock,
        mock_create_custom_instructions: MagicMock,
        mock_fee_address: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
        mock_make_deposit_postings: MagicMock,
    ):
        mock_round_decimal.return_value = Decimal("-30")

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_EXTERNAL_FEE_TYPES: ["DISPUTE_FEE", "ATM_WITHDRAWAL_FEE"]}
        )

        mock_get_supported_fee_types.return_value = [sentinel.supported_fee_types]
        mock_determine_amount_breakdown.return_value = (
            Decimal("-30"),  # credit_line_amount
            Decimal("0"),  # deposit_amount
        )

        mock_make_deposit_postings.return_value = []

        result = credit_card._rebalance_fees(
            vault=sentinel.vault,
            amount=Decimal("-30"),
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            income_account=sentinel.income_account,
            fee_type=sentinel.fee_type,
        )

        self.assertEqual(result, [])
        mock_create_custom_instructions.assert_not_called()
        mock_fee_address.assert_not_called()
        mock_make_internal_address_transfer.assert_not_called()
        mock_make_deposit_postings.assert_called_once_with(
            sentinel.vault,
            sentinel.denomination,
            Decimal("0"),  # deposit_amount
            sentinel.in_flight_balances,
            {"fee_type": sentinel.fee_type},
        )

    def test_positive_fee_amount_and_ci_returned(
        self,
        mock_round_decimal: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_determine_amount_breakdown: MagicMock,
        mock_create_custom_instructions: MagicMock,
        mock_fee_address: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
        mock_make_deposit_postings: MagicMock,
    ):
        mock_round_decimal.return_value = Decimal("200.00")

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_EXTERNAL_FEE_TYPES: ["DISPUTE_FEE", "ATM_WITHDRAWAL_FEE"]}
        )

        mock_get_supported_fee_types.return_value = [sentinel.supported_fee_types]
        mock_determine_amount_breakdown.return_value = (
            Decimal("500"),
            Decimal("200"),
        )
        mock_create_custom_instructions.return_value = [
            SentinelCustomInstruction("rebalance_fees_create_custom_instructions")
        ]
        mock_fee_address.return_value = sentinel.fee_balance_address
        mock_make_internal_address_transfer.return_value = [
            SentinelCustomInstruction("draw_credit")
        ]
        mock_make_deposit_postings.return_value = [SentinelCustomInstruction("deposit_postings")]

        mock_vault = self.create_mock()

        expected_result = [
            SentinelCustomInstruction("rebalance_fees_create_custom_instructions"),
            SentinelCustomInstruction("draw_credit"),
            SentinelCustomInstruction("deposit_postings"),
        ]

        result = credit_card._rebalance_fees(
            vault=mock_vault,
            amount=Decimal("200"),
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            income_account=sentinel.income_account,
            fee_type=sentinel.fee_type,
        )

        self.assertEqual(result, expected_result)


@patch.object(credit_card.utils, "get_parameter")
class GetFeeInternalAccountsTest(CreditCardTestBase):
    def test_get_fee_internal_account_for_txn_type(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                credit_card.PARAM_TXN_TYPE_FEES_INTERNAL_ACCOUNTS_MAP: {
                    "balance_transfer": "FEE_INCOME"
                }
            }
        )

        expected_result = "FEE_INCOME"

        result = credit_card._get_fee_internal_account(
            vault=sentinel.vault,
            txn_type="balance_transfer",
        )

        self.assertEqual(result, expected_result)

    def test_get_fee_internal_account_for_fee_type_is_external_fee(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                credit_card.PARAM_EXTERNAL_FEE_INTERNAL_ACCOUNTS: {"withdrawal_fee": "FEE_INCOME"}
            }
        )

        expected_result = "FEE_INCOME"

        result = credit_card._get_fee_internal_account(
            vault=sentinel.vault,
            fee_type="WITHDRAWAL_FEE",
            is_external_fee=True,
        )

        self.assertEqual(result, expected_result)

    def test_get_fee_internal_account_for_fee_type_is_internal_account(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"annual_fee_internal_account": "annual_fee_internal_account"}
        )

        expected_result = "annual_fee_internal_account"

        result = credit_card._get_fee_internal_account(
            vault=sentinel.vault,
            fee_type="ANNUAL_FEE",
            is_external_fee=False,
        )

        self.assertEqual(result, expected_result)


@patch.object(credit_card, "_update_balances")
@patch.object(credit_card, "move_funds_between_vault_accounts")
@patch.object(credit_card.utils, "get_parameter")
class CreatePostingsTest(CreditCardTestBase):
    def test_create_custom_instructions_amount_zero_no_ci_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_move_funds_between_vault_accounts: MagicMock,
        mock_update_balances: MagicMock,
    ):
        result = credit_card._create_custom_instructions(
            vault=sentinel.vault,
            amount=Decimal("0"),
            debit_account_id=sentinel.debit_account_id,
            credit_account_id=sentinel.debit_account_id,
            denomination=sentinel.denomination,
            debit_address=sentinel.debit_address,
            instruction_details=sentinel.instruction_details,
            credit_address=sentinel.default_address,
            in_flight_balances=sentinel.in_flight_balances,
        )

        self.assertEqual(result, [])
        mock_get_parameter.assert_not_called()
        mock_move_funds_between_vault_accounts.assert_not_called()
        mock_update_balances.assert_not_called()

    def test_create_custom_instructions_without_inflight_balances_ci_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_move_funds_between_vault_accounts: MagicMock,
        mock_update_balances: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_DENOMINATION: sentinel.denomination}
        )
        mock_move_funds_between_vault_accounts.return_value = [
            SentinelCustomInstruction("move_funds_between_vault_accounts")
        ]
        mock_update_balances.return_value = None

        expected_result = [SentinelCustomInstruction("move_funds_between_vault_accounts")]

        result = credit_card._create_custom_instructions(
            vault=sentinel.vault,
            amount=sentinel.amount,
            debit_account_id=sentinel.debit_account_id,
            credit_account_id=sentinel.debit_account_id,
            denomination=sentinel.denomination,
            debit_address=sentinel.debit_address,
            instruction_details=sentinel.instruction_details,
            credit_address=sentinel.credit_address,
            in_flight_balances=None,
        )

        self.assertEqual(result, expected_result)

    def test_create_custom_instructions_with_inflight_balances_ci_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_move_funds_between_vault_accounts: MagicMock,
        mock_update_balances: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_DENOMINATION: sentinel.denomination}
        )
        mock_move_funds_between_vault_accounts.return_value = [
            SentinelCustomInstruction("move_funds_between_vault_accounts")
        ]
        mock_update_balances.return_value = None

        mock_vault = self.create_mock()

        expected_result = [SentinelCustomInstruction("move_funds_between_vault_accounts")]

        result = credit_card._create_custom_instructions(
            vault=mock_vault,
            amount=sentinel.amount,
            debit_account_id=sentinel.debit_account_id,
            credit_account_id=sentinel.debit_account_id,
            denomination=sentinel.denomination,
            debit_address=sentinel.debit_address,
            instruction_details=sentinel.instruction_details,
            credit_address=DEFAULT_ADDRESS,
            in_flight_balances=sentinel.in_flight_balances,
        )

        self.assertEqual(result, expected_result)


class MoveFundsBetweenVaultAccountsTest(CreditCardTestBase):
    def test_move_funds_between_vault_accounts_ci_returned(self):
        expected_result = [
            CustomInstruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("25"),
                        denomination=sentinel.denomination,
                        account_id=sentinel.credit_account_id,
                        account_address=sentinel.credit_address,
                        asset=sentinel.asset,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("25"),
                        denomination=sentinel.denomination,
                        account_id=sentinel.debit_account_id,
                        account_address=sentinel.debit_address,
                        asset=sentinel.asset,
                        phase=Phase.COMMITTED,
                    ),
                ],
                instruction_details={},
                transaction_code=None,
                override_all_restrictions=None,
            )
        ]

        result = credit_card.move_funds_between_vault_accounts(
            amount=Decimal("25"),
            denomination=sentinel.denomination,
            debit_account_id=sentinel.debit_account_id,
            debit_address=sentinel.debit_address,
            credit_account_id=sentinel.credit_account_id,
            credit_address=sentinel.credit_address,
            asset=sentinel.asset,
        )
        self.assertEqual(result, expected_result)


class DeepCopyBalancesTest(CreditCardTestBase):
    def test_deep_copy_balances(self):
        test_balance = Balance(net=Decimal("1"))
        test_balance_coordinate = BalanceCoordinate(
            account_address=credit_card.REVOLVER_BALANCE,
            asset=DEFAULT_ASSET,
            denomination=sentinel.denomination,
            phase=Phase.COMMITTED,
        )
        test_balances = BalanceDefaultDict(None, {test_balance_coordinate: test_balance})

        expected_result = test_balances

        result = credit_card._deep_copy_balances(
            balances=test_balances,
        )

        self.assertEqual(result, expected_result)


class FeeAddressTest(CreditCardTestBase):
    def test_fee_address_returns_balance_address(self):
        expected_result = "MOCK_FEES_CHARGED"

        result = credit_card._fee_address(
            fee_type="MOCK_FEE",
            fee_status="CHARGED",
        )

        self.assertEqual(result, expected_result)


@patch.object(credit_card, "_make_internal_address_transfer")
class MakeDepositPostingsTest(CreditCardTestBase):
    def test_zero_amount_and_no_ci_returned(
        self,
        mock_make_internal_address_transfer: MagicMock,
    ):
        result = credit_card._make_deposit_postings(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            amount=Decimal("0"),
            in_flight_balances=sentinel.in_flight_balances,
            instruction_details=sentinel.instruction_details,
        )

        self.assertEqual(result, [])
        mock_make_internal_address_transfer.assert_not_called()

    def test_non_zero_amount_and_ci_returned(
        self,
        mock_make_internal_address_transfer: MagicMock,
    ):
        mock_make_internal_address_transfer.return_value = [
            SentinelCustomInstruction("internal_transfer")
        ]

        expected_result = [SentinelCustomInstruction("internal_transfer")]

        result = credit_card._make_deposit_postings(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            amount=sentinel.amount,
            in_flight_balances=sentinel.in_flight_balances,
            instruction_details=sentinel.instruction_details,
        )

        self.assertEqual(result, expected_result)


@patch.object(credit_card, "_create_custom_instructions")
class MakeInternalAddressTransferTest(CreditCardTestBase):
    def test_negative_amount_and_no_ci_returned(
        self,
        mock_create_custom_instructions: MagicMock,
    ):
        result = credit_card._make_internal_address_transfer(
            vault=sentinel.vault,
            amount=Decimal("-30"),
            denomination=sentinel.denomination,
            credit_internal=sentinel.credit_internal,
            custom_address=sentinel.custom_address,
        )

        self.assertEqual(result, [])
        mock_create_custom_instructions.assert_not_called()

    def test_zero_or_positive_amount_and_ci_returned(
        self,
        mock_create_custom_instructions: MagicMock,
    ):
        mock_create_custom_instructions.return_value = [
            SentinelCustomInstruction("create_postings")
        ]
        mock_vault = self.create_mock()

        expected_result = [SentinelCustomInstruction("create_postings")]
        result = credit_card._make_internal_address_transfer(
            vault=mock_vault,
            amount=Decimal("10"),
            denomination=sentinel.denomination,
            credit_internal=sentinel.credit_internal,
            custom_address=sentinel.custom_address,
        )

        self.assertEqual(result, expected_result)


@patch.object(credit_card.utils, "balance_at_coordinates")
class DetermineAmountBreakdownTest(CreditCardTestBase):
    def test_charge_amount_with_no_deposit_balance_spent_from_credit_line(
        self,
        mock_balance_at_coordinates: MagicMock,
    ):
        charge_amount = Decimal("12")
        available_deposit = Decimal("0")
        expected_deposit_amount = Decimal("0")
        expected_credit_line_amount = Decimal("12")

        mock_balance_at_coordinates.return_value = available_deposit

        expected_result = expected_credit_line_amount, expected_deposit_amount

        result = credit_card._determine_amount_breakdown(
            amount_to_charge=charge_amount,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
        )

        self.assertEqual(result, expected_result)

    def test_charge_amount_less_than_deposit_balance_spent_from_deposit(
        self,
        mock_balance_at_coordinates: MagicMock,
    ):
        charge_amount = Decimal("12")
        available_deposit = Decimal("50")
        expected_deposit_amount = Decimal("12")
        expected_credit_line_amount = Decimal("0")

        mock_balance_at_coordinates.return_value = available_deposit

        expected_result = expected_credit_line_amount, expected_deposit_amount

        result = credit_card._determine_amount_breakdown(
            amount_to_charge=charge_amount,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
        )

        self.assertEqual(result, expected_result)

    def test_charge_amount_equal_to_deposit_balance_spent_from_deposit(
        self,
        mock_balance_at_coordinates: MagicMock,
    ):
        charge_amount = Decimal("12")
        available_deposit = Decimal("12")
        expected_deposit_amount = Decimal("12")
        expected_credit_line_amount = Decimal("0")

        mock_balance_at_coordinates.return_value = available_deposit

        expected_result = expected_credit_line_amount, expected_deposit_amount

        result = credit_card._determine_amount_breakdown(
            amount_to_charge=charge_amount,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
        )

        self.assertEqual(result, expected_result)

    def test_charge_amount_greater_than_deposit_balance_spent_from_deposit_and_credit_line(
        self,
        mock_balance_at_coordinates: MagicMock,
    ):
        charge_amount = Decimal("20")
        available_deposit = Decimal("12")
        expected_deposit_amount = Decimal("12")
        expected_credit_line_amount = Decimal("8")

        mock_balance_at_coordinates.return_value = available_deposit

        expected_result = expected_credit_line_amount, expected_deposit_amount

        result = credit_card._determine_amount_breakdown(
            amount_to_charge=charge_amount,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
        )

        self.assertEqual(result, expected_result)


class GetSCODForPDDTest(CreditCardTestBase):
    def test_get_scod_for_pdd(self):
        scod_start = DEFAULT_DATETIME - relativedelta(days=21)
        expected_result = (scod_start, scod_start + relativedelta(days=1))

        result = credit_card._get_scod_for_pdd(payment_due_period=21, pdd_start=DEFAULT_DATETIME)

        self.assertEqual(result, expected_result)


class GetFirstPDDTest(CreditCardTestBase):
    def test_get_first_pdd(self):
        first_pdd_start = DEFAULT_DATETIME + relativedelta(days=21)
        expected_result = (first_pdd_start, first_pdd_start + relativedelta(days=1))
        result = credit_card._get_first_pdd(
            payment_due_period=21, first_scod_start=DEFAULT_DATETIME
        )
        self.assertEqual(result, expected_result)


class GetPreviousSCODTest(CreditCardTestBase):
    def test_last_scod_execution_time(self):
        # create mocks
        mock_vault = self.create_mock(
            last_execution_datetimes={credit_card.EVENT_SCOD: DEFAULT_DATETIME}
        )
        account_creation_date = DEFAULT_DATETIME
        last_scod_execution_time = DEFAULT_DATETIME

        # construct expected results
        prev_scod_end = last_scod_execution_time
        prev_scod_start = prev_scod_end - relativedelta(days=1)

        expected_result = (prev_scod_start, prev_scod_end)

        result = credit_card._get_previous_scod(mock_vault, account_creation_date)

        self.assertEqual(result, expected_result)

    def test_no_last_scod_execution_time(self):
        # create mocks
        mock_vault = self.create_mock(last_execution_datetimes={credit_card.EVENT_SCOD: None})
        account_creation_date = DEFAULT_DATETIME

        # construct expected results
        expected_result = (account_creation_date, account_creation_date)

        result = credit_card._get_previous_scod(mock_vault, account_creation_date)

        self.assertEqual(result, expected_result)


class CanFinalStatementBeGeneratedTest(CreditCardTestBase):
    def test_no_account_closure_or_write_off_flags(self):
        # construct values
        balances = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(
                    account_address="TEST_ADDRESS", denomination=self.default_denomination
                ): self.balance(debit=Decimal("100"), credit=Decimal("0"))
            }
        )
        are_closure_flags_applied = False
        are_write_off_flags_applied = False

        expected_result = Rejection(
            message="No account closure or write-off flags on the account",
            reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
        )

        # run function
        result = credit_card._can_final_statement_be_generated(
            balances,
            are_closure_flags_applied,
            are_write_off_flags_applied,
            self.default_denomination,
        )
        self.assertEqual(expected_result, result)

    def test_account_closure_non_zero_balance(self):
        # construct values
        balances = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(
                    account_address=credit_card.FULL_OUTSTANDING_BALANCE,
                    denomination=self.default_denomination,
                ): self.balance(debit=Decimal("100"), credit=Decimal("0"))
            }
        )
        are_closure_flags_applied = True
        are_write_off_flags_applied = False

        expected_result = Rejection(
            message="Full Outstanding Balance is not zero",
            reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
        )

        # run function
        result = credit_card._can_final_statement_be_generated(
            balances,
            are_closure_flags_applied,
            are_write_off_flags_applied,
            self.default_denomination,
        )
        self.assertEqual(expected_result, result)

    def test_account_closure_non_zero_auth(self):
        # construct values
        balances = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(
                    account_address="AUTH", denomination=self.default_denomination
                ): self.balance(debit=Decimal("100"), credit=Decimal("0"))
            }
        )
        are_closure_flags_applied = True
        are_write_off_flags_applied = False

        expected_result = Rejection(
            message="Outstanding authorisations on the account",
            reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
        )

        # run function
        result = credit_card._can_final_statement_be_generated(
            balances,
            are_closure_flags_applied,
            are_write_off_flags_applied,
            self.default_denomination,
        )
        self.assertEqual(expected_result, result)

    def test_account_closure_with_writeoff_flag(self):
        # construct values
        balances = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(
                    account_address="TEST_ADDRESS", denomination=self.default_denomination
                ): self.balance(debit=Decimal("0"), credit=Decimal("0"))
            }
        )
        are_closure_flags_applied = True
        are_write_off_flags_applied = True

        expected_result = None

        # run function
        result = credit_card._can_final_statement_be_generated(
            balances,
            are_closure_flags_applied,
            are_write_off_flags_applied,
            self.default_denomination,
        )
        self.assertEqual(expected_result, result)


class CalculateMadTest(CreditCardTestBase):
    def setUp(self) -> None:
        # mock vault
        self.mock_vault = sentinel.vault

        # is flag in list applied
        patch_is_flag_in_list_applied = patch.object(credit_card.utils, "is_flag_in_list_applied")
        self.mock_is_flag_in_list_applied = patch_is_flag_in_list_applied.start()
        self.mock_is_flag_in_list_applied.return_value = False

        # get supported fee types
        patch_get_supported_fee_types = patch.object(credit_card, "_get_supported_fee_types")
        self.mock_get_supported_fee_types = patch_get_supported_fee_types.start()
        self.mock_get_supported_fee_types.return_value = sentinel.supported_fee_types

        # get parameter
        patch_get_parameter = patch.object(credit_card.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                credit_card.PARAM_MINIMUM_PERCENTAGE_DUE: sentinel.min_percentage_due,
                credit_card.PARAM_MAD: 0.5,
                credit_card.PARAM_CREDIT_LIMIT: sentinel.credit_limit,
            }
        )

        # calculate percentage mad
        patch_calculate_percentage_mad = patch.object(credit_card, "_calculate_percentage_mad")
        self.mock_calculate_percentage_mad = patch_calculate_percentage_mad.start()
        self.mock_calculate_percentage_mad.return_value = Decimal("1.01")

        # round decimal
        patch_round_decimal = patch.object(credit_card.utils, "round_decimal")
        self.mock_round_decimal = patch_round_decimal.start()
        self.mock_round_decimal.return_value = Decimal("1.12")

        # clean up - runs after each test is complete
        self.addCleanup(patch.stopall)

        return super().setUp()

    def test_statement_amount_zero(self):
        # construct inputs
        in_flight_balances = sentinel.in_flight_balances
        denomination = self.default_denomination
        txn_types = sentinel.txn_types
        effective_date = DEFAULT_DATETIME
        statement_amount = Decimal("0")
        mad_eq_statement = sentinel.mad_eq_statement

        # construct expected result
        expected_result = Decimal("0")

        # run calculate mad
        result = credit_card._calculate_mad(
            self.mock_vault,
            in_flight_balances,
            denomination,
            txn_types,
            effective_date,
            statement_amount,
            mad_eq_statement,
        )

        # assert results
        self.assertEqual(result, expected_result)

        # assert calls
        self.mock_is_flag_in_list_applied.assert_not_called()
        self.mock_get_supported_fee_types.assert_not_called()
        self.mock_calculate_percentage_mad.assert_not_called()
        self.mock_round_decimal.assert_not_called()

    def test_mad_equal_to_zero_flag_is_present(self):
        # Update is_flag_in_list_applied return value to True
        self.mock_is_flag_in_list_applied.return_value = True

        # construct inputs
        in_flight_balances = sentinel.in_flight_balances
        denomination = self.default_denomination
        txn_types = sentinel.txn_types
        effective_date = DEFAULT_DATETIME
        statement_amount = Decimal("1")  # Statement amount must be greater than 0
        mad_eq_statement = sentinel.mad_eq_statement

        # construct expected result
        expected_result = Decimal("0")

        # run calculate mad
        result = credit_card._calculate_mad(
            self.mock_vault,
            in_flight_balances,
            denomination,
            txn_types,
            effective_date,
            statement_amount,
            mad_eq_statement,
        )

        # assert results
        self.assertEqual(result, expected_result)

        # assert calls
        self.mock_is_flag_in_list_applied.assert_called_with(
            vault=self.mock_vault,
            parameter_name=credit_card.PARAM_MAD_EQUAL_TO_ZERO_FLAGS,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.mock_get_supported_fee_types.assert_not_called()
        self.mock_calculate_percentage_mad.assert_not_called()
        self.mock_round_decimal.assert_not_called()

    def test_mad_eq_statement_is_true(self):
        # construct inputs
        in_flight_balances = sentinel.in_flight_balances
        denomination = self.default_denomination
        txn_types = sentinel.txn_types
        effective_date = DEFAULT_DATETIME
        statement_amount = Decimal("2")
        mad_eq_statement = True

        # construct expected result
        expected_result = Decimal("2")

        # run calculate mad
        result = credit_card._calculate_mad(
            self.mock_vault,
            in_flight_balances,
            denomination,
            txn_types,
            effective_date,
            statement_amount,
            mad_eq_statement,
        )

        # assert results
        self.assertEqual(result, expected_result)

        # assert calls
        self.mock_is_flag_in_list_applied.assert_called_with(
            vault=self.mock_vault,
            parameter_name=credit_card.PARAM_MAD_EQUAL_TO_ZERO_FLAGS,
            effective_datetime=effective_date,
        )
        self.mock_get_supported_fee_types.assert_not_called()
        self.mock_calculate_percentage_mad.assert_not_called()
        self.mock_round_decimal.assert_not_called()

    def test_percentage_mad(self):
        # construct inputs
        in_flight_balances = sentinel.in_flight_balances
        denomination = self.default_denomination
        txn_types = sentinel.txn_types
        effective_date = DEFAULT_DATETIME
        statement_amount = Decimal("2")
        mad_eq_statement = False

        # construct expected result
        expected_result = Decimal("1.12")
        result = credit_card._calculate_mad(
            self.mock_vault,
            in_flight_balances,
            denomination,
            txn_types,
            effective_date,
            statement_amount,
            mad_eq_statement,
        )

        # assert results
        self.assertEqual(result, expected_result)

        # assert calls
        self.mock_is_flag_in_list_applied.assert_called_with(
            vault=self.mock_vault,
            parameter_name=credit_card.PARAM_MAD_EQUAL_TO_ZERO_FLAGS,
            effective_datetime=effective_date,
        )
        self.mock_get_supported_fee_types.assert_called_with(self.mock_vault, sentinel.txn_types)
        self.mock_calculate_percentage_mad.assert_called_with(
            in_flight_balances,
            denomination,
            sentinel.min_percentage_due,
            sentinel.txn_types,
            sentinel.supported_fee_types,
            sentinel.credit_limit,
        )
        self.mock_round_decimal.assert_called_with(Decimal("1.01"), 2)

    def test_fixed_mad(self):
        # update fixed_mad return value
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                credit_card.PARAM_MINIMUM_PERCENTAGE_DUE: sentinel.min_percentage_due,
                credit_card.PARAM_MAD: Decimal("1.5"),
                credit_card.PARAM_CREDIT_LIMIT: sentinel.credit_limit,
            }
        )

        # update calculate percentage mad return value
        self.mock_calculate_percentage_mad.return_value = Decimal("0")

        # update round decimal return value
        self.mock_round_decimal.return_value = Decimal("1.5")

        # construct inputs
        in_flight_balances = sentinel.in_flight_balances
        denomination = self.default_denomination
        txn_types = sentinel.txn_types
        effective_date = DEFAULT_DATETIME
        statement_amount = Decimal("2")
        mad_eq_statement = False

        # construct expected result
        expected_result = Decimal("1.5")

        # run calculate mad
        result = credit_card._calculate_mad(
            self.mock_vault,
            in_flight_balances,
            denomination,
            txn_types,
            effective_date,
            statement_amount,
            mad_eq_statement,
        )

        # assert results
        self.assertEqual(result, expected_result)

        # assert calls
        self.mock_is_flag_in_list_applied.assert_called_with(
            vault=self.mock_vault,
            parameter_name=credit_card.PARAM_MAD_EQUAL_TO_ZERO_FLAGS,
            effective_datetime=effective_date,
        )
        self.mock_get_supported_fee_types.assert_called_with(self.mock_vault, sentinel.txn_types)
        self.mock_calculate_percentage_mad.assert_called_with(
            in_flight_balances,
            denomination,
            sentinel.min_percentage_due,
            sentinel.txn_types,
            sentinel.supported_fee_types,
            sentinel.credit_limit,
        )
        self.mock_round_decimal.assert_called_with(Decimal("1.5"), 2)


@patch.object(credit_card, "_rebalance_balance_buckets")
@patch.object(credit_card, "_interest_address")
class BillChargedInterestTest(CreditCardTestBase):
    def test_bill_charged_interest(
        self,
        mock_interest_address: MagicMock,
        mock_rebalance_balance_buckets: MagicMock,
    ):
        # construct values
        rebalance_postings_1 = [SentinelCustomInstruction("rebalance_postings_1")]
        rebalance_postings_2 = [SentinelCustomInstruction("rebalance_postings_2")]
        supported_txn_types: dict[str, Optional[list[str]]] = {
            "PURCHASE": [sentinel.txn_ref],
        }
        supported_fee_types = [
            "ANNUAL_FEE",
        ]
        expected_result = [*rebalance_postings_1, *rebalance_postings_2]

        # construct mocks
        mock_interest_address.side_effect = [
            sentinel.from_balance_address_1,
            sentinel.to_balance_address_1,
            sentinel.from_balance_address_2,
            sentinel.to_balance_address_2,
        ]
        mock_rebalance_balance_buckets.side_effect = [
            (
                sentinel._,
                rebalance_postings_1,
            ),
            (
                sentinel._,
                rebalance_postings_2,
            ),
        ]

        # run function
        result = credit_card._bill_charged_interest(
            vault=sentinel.vault,
            supported_fee_types=supported_fee_types,
            supported_txn_types=supported_txn_types,
            denomination=self.default_denomination,
            in_flight_balances=sentinel.in_flight_balances,
        )
        self.assertEqual(expected_result, result)

        # assert calls
        mock_interest_address.assert_has_calls(
            calls=[
                call(
                    "PURCHASE",
                    "CHARGED",
                    txn_ref=sentinel.txn_ref,
                ),
                call(
                    "PURCHASE",
                    "BILLED",
                    txn_ref=sentinel.txn_ref,
                ),
                call(
                    "ANNUAL_FEE",
                    "CHARGED",
                    txn_ref=None,
                ),
                call(
                    "ANNUAL_FEE",
                    "BILLED",
                    txn_ref=None,
                ),
            ]
        )
        mock_rebalance_balance_buckets.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.vault,
                    in_flight_balances=sentinel.in_flight_balances,
                    debit_address=sentinel.from_balance_address_1,
                    credit_address=sentinel.to_balance_address_1,
                    denomination=self.default_denomination,
                ),
                call(
                    vault=sentinel.vault,
                    in_flight_balances=sentinel.in_flight_balances,
                    debit_address=sentinel.from_balance_address_2,
                    credit_address=sentinel.to_balance_address_2,
                    denomination=self.default_denomination,
                ),
            ]
        )


class GetSettlementInfoTest(CreditCardTestBase):
    @patch.object(credit_card, "_get_unsettled_amount")
    def test_get_settlement_info(self, mock_get_unsettled_amount: MagicMock):
        mock_vault = self.create_mock()
        mock_get_unsettled_amount.return_value = Decimal("0")

        test_postings = [
            Posting(
                credit=True,
                amount=Decimal("200"),
                denomination=self.default_denomination,
                account_id="1",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
            Posting(
                credit=False,
                amount=Decimal("200"),
                denomination=self.default_denomination,
                account_id=mock_vault.account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                phase=Phase.COMMITTED,
            ),
        ]

        test_posting_instruction = self.custom_instruction(postings=test_postings)

        expected_result = (Decimal("200"), mock_get_unsettled_amount.return_value)
        result = credit_card._get_settlement_info(
            mock_vault,
            self.default_denomination,
            posting_instruction=test_posting_instruction,
            client_transaction=None,
            account_id=ACCOUNT_ID,
        )

        self.assertEqual(result, expected_result)


@patch.object(credit_card, "_make_internal_address_transfer")
class ZeroOutMadBalance(CreditCardTestBase):
    def test_zero_mad_balance_and_no_ci_returned(
        self,
        mock_make_internal_address_transfer: MagicMock,
    ):
        result = credit_card._zero_out_mad_balance(
            vault=sentinel.vault,
            mad_balance=Decimal("0"),
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, [])
        mock_make_internal_address_transfer.assert_not_called()

    def test_positive_mad_balance_and_no_ci_returned(
        self,
        mock_make_internal_address_transfer: MagicMock,
    ):
        zero_out_mad_instruction = [SentinelCustomInstruction("zero out mad balance")]
        mock_make_internal_address_transfer.return_value = zero_out_mad_instruction

        expected_result = zero_out_mad_instruction

        result = credit_card._zero_out_mad_balance(
            vault=sentinel.vault,
            mad_balance=Decimal("100"),
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, expected_result)
        mock_make_internal_address_transfer.assert_called_once_with(
            vault=sentinel.vault,
            amount=Decimal("100"),
            denomination=sentinel.denomination,
            credit_internal=False,
            custom_address=credit_card.MAD_BALANCE,
            instruction_details={"description": "PARAM_MAD balance zeroed out"},
        )


@patch.object(credit_card, "_calculate_aggregate_balance")
class GetOutstandingStatmentAmount(CreditCardTestBase):
    def test_amount_returned(
        self,
        mock_calculate_aggregate_balance: MagicMock,
    ):
        # construct mocks
        mock_calculate_aggregate_balance.return_value = sentinel.aggregate_balance_amount

        # expected_result
        expected_result = sentinel.aggregate_balance_amount

        # run function
        result = credit_card._get_outstanding_statement_amount(
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            fee_types=sentinel.fee_types,
            txn_types=sentinel.txn_types,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_calculate_aggregate_balance.assert_called_once_with(
            sentinel.balances,
            sentinel.denomination,
            sentinel.fee_types,
            balance_def={
                credit_card.PRINCIPAL: credit_card.STATEMENT_BALANCE_STATES,
                credit_card.INTEREST: credit_card.STATEMENT_BALANCE_STATES,
                credit_card.FEES: credit_card.STATEMENT_BALANCE_STATES,
            },
            include_deposit=True,
            txn_type_map=sentinel.txn_types,
        )


@patch.object(credit_card, "_move_funds_internally")
@patch.object(credit_card.utils, "balance_at_coordinates")
class RebalanceBalanceBucketsTest(CreditCardTestBase):
    def test_zero_amount_and_no_ci_returned(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_move_funds_internally: MagicMock,
    ):
        mock_balance_at_coordinates.return_value = Decimal("0")

        expected_result: tuple[Decimal, list[CustomInstruction]] = Decimal("0"), []

        result = credit_card._rebalance_balance_buckets(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            debit_address=sentinel.debit_address,
            credit_address=sentinel.credit_address,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, expected_result)
        mock_move_funds_internally.assert_not_called()

    def test_non_zero_amount_and_amount_with_ci_returned(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_move_funds_internally: MagicMock,
    ):
        rebalance_amount = Decimal("-25")
        rebalance_postings = [SentinelCustomInstruction("rebalance postings")]
        mock_balance_at_coordinates.return_value = rebalance_amount
        mock_move_funds_internally.return_value = rebalance_postings

        expected_result = rebalance_amount, rebalance_postings

        result = credit_card._rebalance_balance_buckets(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            debit_address=sentinel.debit_address,
            credit_address=sentinel.credit_address,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, expected_result)
        mock_move_funds_internally.assert_called_once_with(
            sentinel.vault,
            abs(rebalance_amount),
            sentinel.credit_address,
            sentinel.debit_address,
            sentinel.denomination,
            sentinel.in_flight_balances,
        )


@patch.object(credit_card.utils, "get_parameter")
class GetInterestInternalAccounts(CreditCardTestBase):
    def test_fees_interest_internal_account_returned(
        self,
        mock_get_parameter: MagicMock,
    ):
        fee_interest_income_account = sentinel.interest_on_fees_internal_account

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                credit_card.PARAM_INTEREST_ON_FEES_INTERNAL_ACCOUNT: fee_interest_income_account
            }
        )

        expected_result = fee_interest_income_account

        result = credit_card._get_interest_internal_accounts(
            vault=sentinel.vault,
            charge_type="FEES",
            sub_type=sentinel.sub_type,
        )

        self.assertEqual(result, expected_result)

    def test_non_fees_interest_internal_account_returned(
        self,
        mock_get_parameter: MagicMock,
    ):
        internal_accounts_map = {
            "sentinel.sub_type1": "sentinel.interest_internal_account1",
            "sentinel.sub_type2": "sentinel.interest_internal_account2",
        }

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                credit_card.PARAM_TXN_TYPE_INTEREST_INTERNAL_ACCOUNTS_MAP: internal_accounts_map
            }
        )

        expected_result = "sentinel.interest_internal_account2"

        result = credit_card._get_interest_internal_accounts(
            vault=sentinel.vault,
            charge_type=sentinel.charge_type,
            sub_type="SENTINEL.SUB_TYPE2",
        )

        self.assertEqual(result, expected_result)


@patch.object(credit_card.utils, "get_parameter")
class IsTxnInterestAccrualFromTxnDayTest(CreditCardTestBase):
    def test_accrue_interest_from_txn_day_and_true_returned(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_ACCRUE_INTEREST_FROM_TXN_DAY: True}
        )

        result = credit_card._is_txn_interest_accrual_from_txn_day(
            vault=sentinel.vault,
        )

        self.assertTrue(result)

    def test_accrue_interest_from_txn_day_and_false_returned(
        self,
        mock_get_parameter: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_ACCRUE_INTEREST_FROM_TXN_DAY: False}
        )

        result = credit_card._is_txn_interest_accrual_from_txn_day(
            vault=sentinel.vault,
        )
        print(result, type(result))
        self.assertFalse(result)


class IsTxnTypeInInterestFreePeriodTest(CreditCardTestBase):
    txn_types_in_interest_free_period = {
        "txn_type_1": ["REF1", "REF2"],
        "txn_type_2": ["REF8", "REF9"],
        "txn_type_3": None,
    }

    def test_interest_free_period_txn_type_and_true_returned(self):
        result = credit_card._is_txn_type_in_interest_free_period(
            txn_types_in_interest_free_period=self.txn_types_in_interest_free_period,
            sub_type="TXN_TYPE_2",
            ref=None,
        )

        self.assertTrue(result)

    def test_non_interest_free_period_txn_type_and_false_returned(self):
        result = credit_card._is_txn_type_in_interest_free_period(
            txn_types_in_interest_free_period=self.txn_types_in_interest_free_period,
            sub_type="TXN_TYPE_NOT_INTEREST_FREE",
            ref=None,
        )
        self.assertFalse(result)

    def test_interest_free_period_txn_type_with_ref_and_true_returned(self):
        result = credit_card._is_txn_type_in_interest_free_period(
            txn_types_in_interest_free_period=self.txn_types_in_interest_free_period,
            sub_type="TXN_TYPE_2",
            ref="REF9",
        )

        self.assertTrue(result)

    def test_interest_free_period_txn_type_with_wrong_ref_and_false_returned(self):
        result = credit_card._is_txn_type_in_interest_free_period(
            txn_types_in_interest_free_period=self.txn_types_in_interest_free_period,
            sub_type="TXN_TYPE_2",
            ref="REF_NOT_INTEREST_FREE",
        )

        self.assertFalse(result)


@patch.object(credit_card, "_adjust_aggregate_balances")
@patch.object(credit_card, "_charge_fee")
@patch.object(credit_card, "_get_overlimit_amount")
@patch.object(credit_card.utils, "get_parameter")
@patch.object(credit_card.utils, "str_to_bool")
class ChargeOverlimitFeeTest(CreditCardTestBase):
    def test_opt_in_true_overlimit_fee_charged_and_ci_returned(
        self,
        mock_str_to_bool: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_overlimit_amount: MagicMock,
        mock_charge_fee: MagicMock,
        mock_adjust_aggregate_balances: MagicMock,
    ):
        # Overlimit opt in True, Overlimit fee 50, Overlimit amount 20
        # construct mocks
        mock_str_to_bool.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_OVERLIMIT_OPT_IN: True}
        )
        mock_get_overlimit_amount.return_value = Decimal("20")
        mock_charge_fee.return_value = Decimal("50"), [
            SentinelCustomInstruction("charge overlimit fee")
        ]
        mock_adjust_aggregate_balances.return_value = [
            SentinelCustomInstruction("adjust aggregate balances")
        ]

        # expected result
        expected_result = [
            SentinelCustomInstruction("charge overlimit fee"),
            SentinelCustomInstruction("adjust aggregate balances"),
        ]

        # run function
        result = credit_card._charge_overlimit_fee(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            denomination=sentinel.denomination,
            supported_txn_types=sentinel.supported_txn_types,
            credit_limit=sentinel.credit_limit,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_get_overlimit_amount.assert_called_once_with(
            sentinel.in_flight_balances,
            sentinel.credit_limit,
            sentinel.denomination,
            sentinel.supported_txn_types,
        )
        mock_charge_fee.assert_called_once_with(
            sentinel.vault,
            sentinel.denomination,
            sentinel.in_flight_balances,
            credit_card.OVERLIMIT_FEE,
        )
        mock_adjust_aggregate_balances.assert_called_once_with(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            outstanding=False,
            full_outstanding=False,
            credit_limit=sentinel.credit_limit,
        )

    def test_opt_in_true_overlimit_zero_fee_and_no_ci_returned(
        self,
        mock_str_to_bool: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_overlimit_amount: MagicMock,
        mock_charge_fee: MagicMock,
        mock_adjust_aggregate_balances: MagicMock,
    ):
        # Overlimit opt in True, Overlimit fee 0, Overlimit amount 20
        # construct mocks
        mock_str_to_bool.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_OVERLIMIT_OPT_IN: True}
        )
        mock_get_overlimit_amount.return_value = Decimal("20")
        mock_charge_fee.return_value = Decimal("0"), []

        # run function
        result = credit_card._charge_overlimit_fee(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            denomination=sentinel.denomination,
            supported_txn_types=sentinel.supported_txn_types,
            credit_limit=sentinel.credit_limit,
        )

        # call assertions
        self.assertEqual(result, [])
        mock_adjust_aggregate_balances.assert_not_called()
        mock_charge_fee.assert_called_once_with(
            sentinel.vault,
            sentinel.denomination,
            sentinel.in_flight_balances,
            credit_card.OVERLIMIT_FEE,
        )

    def test_opt_in_false_overlimit_and_no_ci_returned(
        self,
        mock_str_to_bool: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_overlimit_amount: MagicMock,
        mock_charge_fee: MagicMock,
        mock_adjust_aggregate_balances: MagicMock,
    ):
        # Overlimit opt in False, Overlimit amount 20
        # construct mocks
        mock_str_to_bool.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_OVERLIMIT_OPT_IN: False}
        )
        mock_get_overlimit_amount.return_value = Decimal("20")

        # run function
        result = credit_card._charge_overlimit_fee(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            denomination=sentinel.denomination,
            supported_txn_types=sentinel.supported_txn_types,
            credit_limit=sentinel.credit_limit,
        )

        self.assertEqual(result, [])
        mock_charge_fee.assert_not_called()
        mock_adjust_aggregate_balances.assert_not_called()


@patch.object(credit_card, "_calculate_aggregate_balance")
class GetOverlimitAmountTest(CreditCardTestBase):
    def test_not_overlimit_and_zero_returned(
        self,
        mock_calculate_aggregate_balance: MagicMock,
    ):
        principal_amount = Decimal("20")
        credit_limit = Decimal("100")
        mock_calculate_aggregate_balance.return_value = principal_amount

        expected_result = Decimal("0")

        result = credit_card._get_overlimit_amount(
            balances=sentinel.balances,
            credit_limit=credit_limit,
            denomination=sentinel.denomination,
            supported_txn_types=sentinel.supported_txn_types,
        )

        self.assertEqual(result, expected_result)

    def test_overlimit_and_overlimit_amount_returned(
        self,
        mock_calculate_aggregate_balance: MagicMock,
    ):
        principal_amount = Decimal("250")
        credit_limit = Decimal("100")
        mock_calculate_aggregate_balance.return_value = principal_amount

        expected_result = Decimal("150")

        result = credit_card._get_overlimit_amount(
            balances=sentinel.balances,
            credit_limit=credit_limit,
            denomination=sentinel.denomination,
            supported_txn_types=sentinel.supported_txn_types,
        )

        self.assertEqual(result, expected_result)


@patch.object(credit_card, "_override_info_balance")
@patch.object(credit_card, "_reverse_uncharged_interest")
@patch.object(credit_card, "_is_txn_interest_accrual_from_txn_day")
@patch.object(credit_card.utils, "get_parameter")
class ZeroOutBalancesForAccountClosure(CreditCardTestBase):
    def test_no_accrue_interest_from_txn_day_and_ci_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_is_txn_interest_accrual_from_txn_day: MagicMock,
        mock_reverse_uncharged_interest: MagicMock,
        mock_override_info_balance: MagicMock,
    ):
        # construct values
        accrued_interest_postings = [SentinelCustomInstruction("reverse_uncharged_interest")]
        available_balance_postings = [SentinelCustomInstruction("override_balance_to_zero")]

        expected_result = [*accrued_interest_postings, *available_balance_postings]

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_DENOMINATION: sentinel.denomination}
        )
        mock_is_txn_interest_accrual_from_txn_day.return_value = False
        mock_reverse_uncharged_interest.return_value = accrued_interest_postings
        mock_override_info_balance.return_value = available_balance_postings

        # run function
        result = credit_card._zero_out_balances_for_account_closure(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            in_flight_balances=sentinel.in_flight_balances,
            txn_types=sentinel.txn_types,  # Optional
        )

        # assert calls
        self.assertEqual(result, expected_result)
        mock_reverse_uncharged_interest.assert_called_once_with(
            sentinel.vault,
            sentinel.in_flight_balances,
            sentinel.denomination,
            sentinel.txn_types,
            "ACCOUNT_CLOSED",
        )

    def test_accrue_interest_from_txn_day_and_ci_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_is_txn_interest_accrual_from_txn_day: MagicMock,
        mock_reverse_uncharged_interest: MagicMock,
        mock_override_info_balance: MagicMock,
    ):
        # construct values
        accrued_interest_postings = [SentinelCustomInstruction("reverse_uncharged_interest")]
        accrued_interest_postings_prescod = [
            SentinelCustomInstruction("reverse_uncharged_interest_PRE_SCOD")
        ]
        accrued_interest_postings_postscod = [
            SentinelCustomInstruction("reverse_uncharged_interest_POST_SCOD")
        ]
        available_balance_postings = [SentinelCustomInstruction("override_balance_to_zero")]

        expected_result = [
            *accrued_interest_postings,
            *accrued_interest_postings_prescod,
            *accrued_interest_postings_postscod,
            *available_balance_postings,
        ]

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_DENOMINATION: sentinel.denomination}
        )
        mock_is_txn_interest_accrual_from_txn_day.return_value = True
        mock_reverse_uncharged_interest.side_effect = [
            accrued_interest_postings,
            accrued_interest_postings_prescod,
            accrued_interest_postings_postscod,
        ]
        mock_override_info_balance.return_value = available_balance_postings

        # run function
        result = credit_card._zero_out_balances_for_account_closure(
            vault=sentinel.vault,
            effective_datetime=sentinel.effective_date,
            in_flight_balances=sentinel.in_flight_balances,
            txn_types=sentinel.txn_types,  # Optional
        )

        # assert calls
        self.assertEqual(result, expected_result)
        mock_reverse_uncharged_interest.assert_has_calls(
            calls=[
                call(
                    sentinel.vault,
                    sentinel.in_flight_balances,
                    sentinel.denomination,
                    sentinel.txn_types,
                    "ACCOUNT_CLOSED",
                ),
                call(
                    sentinel.vault,
                    sentinel.in_flight_balances,
                    sentinel.denomination,
                    sentinel.txn_types,
                    "ACCOUNT_CLOSED",
                    credit_card.PRE_SCOD,
                ),
                call(
                    sentinel.vault,
                    sentinel.in_flight_balances,
                    sentinel.denomination,
                    sentinel.txn_types,
                    "ACCOUNT_CLOSED",
                    credit_card.POST_SCOD,
                ),
            ]
        )


@patch.object(credit_card, "_fee_address")
@patch.object(credit_card, "_interest_address")
@patch.object(credit_card, "_principal_address")
class CalculateAggregateBalanceTest(CreditCardTestBase):
    def init_balances(self, balance_defs: list[dict[str, str]]) -> BalanceDefaultDict:
        """
        Returns a BalanceDefaultDict object.
        :param balance_defs: List(dict) the balances to construct. Each def is a dict with
        'address', 'denomination' 'phase' and 'asset' attributes for dimensions and 'net, 'debit',
        and 'credit' for the Balance. Dimensions default to their default value.
        :return: BalanceDefaultDict
        """
        balance_defs = balance_defs or []
        balance_dict = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=balance_def.get("address", DEFAULT_ADDRESS).upper(),
                    asset=balance_def.get("asset", DEFAULT_ASSET),
                    denomination=balance_def.get("denomination", sentinel.denomination),
                    phase=Phase(balance_def.get("phase", Phase.COMMITTED)),
                ): Balance(
                    credit=Decimal(balance_def.get("credit", Decimal("0"))),
                    debit=Decimal(balance_def.get("debit", Decimal("0"))),
                    net=Decimal(balance_def.get("net", Decimal("0"))),
                )
                for balance_def in balance_defs
            },
        )

        return balance_dict

    def setUp(self):
        super().setUp()
        self.balances = self.init_balances(
            balance_defs=[
                # by setting the values at different powers of 10 we can easily see which were
                # included in the calc or not. Organized by deposit, principal, interest, and fees.
                {"address": "DEPOSIT", "net": "10000000000"},
                {"address": "PURCHASE_BILLED", "net": "1"},
                {"address": "CASH_ADVANCE_CHARGED", "net": "10"},
                {"address": "TRANSFER_UNPAID", "net": "100"},
                {"address": "PURCHASE_INTEREST_UNCHARGED", "net": "1000"},
                {"address": "PURCHASE_INTEREST_BILLED", "net": "10000"},
                {"address": "CASH_ADVANCE_INTEREST_CHARGED", "net": "100000"},
                {"address": "TRANSFER_INTEREST_UNPAID", "net": "1000000"},
                {"address": "ANNUAL_FEES_CHARGED", "net": "10000000"},
                {"address": "CASH_ADVANCE_FEES_BILLED", "net": "100000000"},
                {"address": "DISPUTE_FEES_UNPAID", "net": "1000000000"},
            ]
        )

    def test_principal_only(
        self,
        mock_principal_address: MagicMock,
        mock_interest_address: MagicMock,
        mock_fee_address: MagicMock,
    ):
        balance_def = {"PRINCIPAL": ["CHARGED", "BILLED", "UNPAID"]}  # : [txn_states]
        txn_type_map: dict[str, Optional[list[str]]] = {
            "PURCHASE": None,
            "CASH_ADVANCE": None,
            "TRANSFER": None,
        }  # txn_type:txn_ref

        mock_principal_address.side_effect = [
            "PURCHASE_CHARGED",
            "PURCHASE_BILLED",
            "PURCHASE_UNPAID",
            "CASH_ADVANCE_CHARGED",
            "CASH_ADVANCE_BILLED",
            "CASH_ADVANCE_UNPAID",
            "TRANSFER_CHARGED",
            "TRANSFER_BILLED",
            "TRANSFER_UNPAID",
        ]

        # expected = PURCHASE_BILLED + CASH_ADVANCE_CHARGED + TRANSFER_UNPAID - DEPOSIT
        expected_result = Decimal("-9999999889")  # 1 + 10 + 100 - 10000000000 = -9999999889

        results = credit_card._calculate_aggregate_balance(
            balances=self.balances,
            denomination=sentinel.denomination,
            fee_types=[sentinel.fee_types],
            balance_def=balance_def,
            include_deposit=True,
            txn_type_map=txn_type_map,
        )

        self.assertEqual(results, expected_result)
        mock_interest_address.assert_not_called()
        mock_fee_address.assert_not_called()
        mock_principal_address.assert_has_calls(
            calls=[
                call(
                    "PURCHASE",
                    "CHARGED",
                ),
                call(
                    "PURCHASE",
                    "BILLED",
                ),
                call(
                    "PURCHASE",
                    "UNPAID",
                ),
                call(
                    "CASH_ADVANCE",
                    "CHARGED",
                ),
                call(
                    "CASH_ADVANCE",
                    "BILLED",
                ),
                call(
                    "CASH_ADVANCE",
                    "UNPAID",
                ),
                call(
                    "TRANSFER",
                    "CHARGED",
                ),
                call(
                    "TRANSFER",
                    "BILLED",
                ),
                call(
                    "TRANSFER",
                    "UNPAID",
                ),
            ]
        )

    def test_principal_only_and_txn_ref_and_deposit_not_included(
        self,
        mock_principal_address: MagicMock,
        mock_interest_address: MagicMock,
        mock_fee_address: MagicMock,
    ):
        balance_def = {"PRINCIPAL": ["CHARGED", "BILLED", "UNPAID"]}  # : [txn_states]
        txn_type_map = {
            "PURCHASE": ["REF2"],
            "CASH_ADVANCE": None,
            "TRANSFER": None,
        }  # txn_type:txn_ref
        fee_types = ["ANNUAL_FEE", "DISPUTE_FEE"]

        mock_principal_address.side_effect = [
            "PURCHASE_REF2_CHARGED",
            "PURCHASE_REF2_BILLED",
            "PURCHASE_REF2_UNPAID",
            "CASH_ADVANCE_CHARGED",
            "CASH_ADVANCE_BILLED",
            "CASH_ADVANCE_UNPAID",
            "TRANSFER_CHARGED",
            "TRANSFER_BILLED",
            "TRANSFER_UNPAID",
        ]

        # expected = CASH_ADVANCE_CHARGED + TRANSFER_UNPAID.
        expected_result = Decimal("110")  # 10 + 100 = 110

        results = credit_card._calculate_aggregate_balance(
            balances=self.balances,
            denomination=sentinel.denomination,
            fee_types=fee_types,
            balance_def=balance_def,
            include_deposit=False,
            txn_type_map=txn_type_map,
        )

        self.assertEqual(results, expected_result)
        mock_interest_address.assert_not_called()
        mock_fee_address.assert_not_called()

    def test_interest_only(
        self,
        mock_principal_address: MagicMock,
        mock_interest_address: MagicMock,
        mock_fee_address: MagicMock,
    ):
        balance_def = {
            "INTEREST": ["UNCHARGED", "CHARGED", "BILLED", "UNPAID"]
        }  # : [interest_states]
        txn_type_map: dict[str, Optional[list[str]]] = {
            "PURCHASE": None,
            "CASH_ADVANCE": None,
            "TRANSFER": None,
        }  # txn_type:txn_ref
        fee_types = ["ANNUAL_FEE", "DISPUTE_FEE"]

        mock_interest_address.side_effect = [
            "PURCHASE_INTEREST_UNCHARGED",
            "PURCHASE_INTEREST_CHARGED",
            "PURCHASE_INTEREST_BILLED",
            "PURCHASE_INTEREST_UNPAID",
            "CASH_ADVANCE_INTEREST_UNCHARGED",
            "CASH_ADVANCE_INTEREST_CHARGED",
            "CASH_ADVANCE_INTEREST_BILLED",
            "CASH_ADVANCE_INTEREST_UNPAID",
            "TRANSFER_INTEREST_UNCHARGED",
            "TRANSFER_INTEREST_CHARGED",
            "TRANSFER_INTEREST_BILLED",
            "TRANSFER_INTEREST_UNPAID",
            "ANNUAL_FEE_INTEREST_UNCHARGED",
            "ANNUAL_FEE_INTEREST_CHARGED",
            "ANNUAL_FEE_INTEREST_BILLED",
            "ANNUAL_FEE_INTEREST_UNPAID",
            "DISPUTE_FEE_INTEREST_UNCHARGED",
            "DISPUTE_FEE_INTEREST_CHARGED",
            "DISPUTE_FEE_INTEREST_BILLED",
            "DISPUTE_FEE_INTEREST_UNPAID",
        ]

        # expected = PURCHASE_INTEREST_UNCHARGED + PURCHASE_INTEREST_BILLED
        #          + CASH_ADVANCE_INTEREST_CHARGED + TRANSFER_INTEREST_UNPAID - DEPOSIT
        expected_result = Decimal("-9998889000")  # 1000 + 10000 + 100000 + 1000000 - 10000000000

        results = credit_card._calculate_aggregate_balance(
            balances=self.balances,
            denomination=sentinel.denomination,
            fee_types=fee_types,
            balance_def=balance_def,
            include_deposit=True,
            txn_type_map=txn_type_map,
        )

        self.assertEqual(results, expected_result)
        mock_principal_address.assert_not_called()
        mock_fee_address.assert_not_called()
        mock_interest_address.assert_has_calls(
            calls=[
                call(
                    "PURCHASE",
                    "UNCHARGED",
                ),
                call(
                    "PURCHASE",
                    "CHARGED",
                ),
                call(
                    "PURCHASE",
                    "BILLED",
                ),
                call(
                    "PURCHASE",
                    "UNPAID",
                ),
                call(
                    "CASH_ADVANCE",
                    "UNCHARGED",
                ),
                call(
                    "CASH_ADVANCE",
                    "CHARGED",
                ),
                call(
                    "CASH_ADVANCE",
                    "BILLED",
                ),
                call(
                    "CASH_ADVANCE",
                    "UNPAID",
                ),
                call(
                    "TRANSFER",
                    "UNCHARGED",
                ),
                call(
                    "TRANSFER",
                    "CHARGED",
                ),
                call(
                    "TRANSFER",
                    "BILLED",
                ),
                call(
                    "TRANSFER",
                    "UNPAID",
                ),
                call(
                    "ANNUAL_FEE",
                    "UNCHARGED",
                ),
                call(
                    "ANNUAL_FEE",
                    "CHARGED",
                ),
                call(
                    "ANNUAL_FEE",
                    "BILLED",
                ),
                call(
                    "ANNUAL_FEE",
                    "UNPAID",
                ),
                call(
                    "DISPUTE_FEE",
                    "UNCHARGED",
                ),
                call(
                    "DISPUTE_FEE",
                    "CHARGED",
                ),
                call(
                    "DISPUTE_FEE",
                    "BILLED",
                ),
                call(
                    "DISPUTE_FEE",
                    "UNPAID",
                ),
            ]
        )

    def test_fees_only(
        self,
        mock_principal_address: MagicMock,
        mock_interest_address: MagicMock,
        mock_fee_address: MagicMock,
    ):
        balance_def = {"FEES": ["CHARGED", "BILLED", "UNPAID"]}  # : [fee_states]
        fee_types = ["ANNUAL_FEE", "DISPUTE_FEE"]

        mock_fee_address.side_effect = [
            "ANNUAL_FEES_CHARGED",
            "ANNUAL_FEES_BILLED",
            "ANNUAL_FEES_UNPAID",
            "DISPUTE_FEES_CHARGED",
            "DISPUTE_FEES_BILLED",
            "DISPUTE_FEES_UNPAID",
        ]

        # expected = ANNUAL_FEES_CHARGED + DISPUTE_FEES_UNPAID  - DEPOSIT
        expected_result = Decimal("-8990000000")  # 10000000 + 1000000000 - 10000000000

        results = credit_card._calculate_aggregate_balance(
            balances=self.balances,
            denomination=sentinel.denomination,
            fee_types=fee_types,
            balance_def=balance_def,
            include_deposit=True,
            txn_type_map={sentinel.txn_type: sentinel.txn_ref},
        )

        self.assertEqual(results, expected_result)
        mock_principal_address.assert_not_called()
        mock_interest_address.assert_not_called()
        mock_fee_address.assert_has_calls(
            calls=[
                call(
                    "ANNUAL_FEE",
                    "CHARGED",
                ),
                call(
                    "ANNUAL_FEE",
                    "BILLED",
                ),
                call(
                    "ANNUAL_FEE",
                    "UNPAID",
                ),
                call(
                    "DISPUTE_FEE",
                    "CHARGED",
                ),
                call(
                    "DISPUTE_FEE",
                    "BILLED",
                ),
                call(
                    "DISPUTE_FEE",
                    "UNPAID",
                ),
            ]
        )

    def test_mixed_states_and_balance_types(
        self,
        mock_principal_address: MagicMock,
        mock_interest_address: MagicMock,
        mock_fee_address: MagicMock,
    ):
        balance_def = {
            "FEES": ["UNPAID"],
            "INTEREST": ["BILLED"],
            "PRINCIPAL": ["CHARGED"],
        }  # : [states]
        txn_type_map: dict[str, Optional[list[str]]] = {
            "PURCHASE": None,
            "CASH_ADVANCE": None,
            "TRANSFER": None,
        }  # txn_type:txn_ref
        fee_types = ["ANNUAL_FEE", "DISPUTE_FEE"]

        mock_principal_address.side_effect = [
            "PURCHASE_CHARGED",
            "CASH_ADVANCE_CHARGED",
            "TRANSFER_CHARGED",
        ]
        mock_interest_address.side_effect = [
            "PURCHASE_INTEREST_BILLED",
            "CASH_ADVANCE_INTEREST_BILLED",
            "TRANSFER_INTEREST_BILLED",
            "ANNUAL_FEE_INTEREST_BILLED",
            "DISPUTE_FEE_INTEREST_BILLED",
        ]
        mock_fee_address.side_effect = [
            "ANNUAL_FEES_UNPAID",
            "DISPUTE_FEES_UNPAID",
        ]

        # expected = CASH_ADVANCE_CHARGED + PURCHASE_INTEREST_BILLED + DISPUTE_FEES_UNPAID
        #          - DEPOSIT
        expected_result = Decimal("-8999989990")  # 10 + 10000 + 1000000000 - 10000000000

        results = credit_card._calculate_aggregate_balance(
            balances=self.balances,
            denomination=sentinel.denomination,
            fee_types=fee_types,
            balance_def=balance_def,
            include_deposit=True,
            txn_type_map=txn_type_map,
        )

        self.assertEqual(results, expected_result)

    def test_mixed_states_and_balance_types_deposit_not_included(
        self,
        mock_principal_address: MagicMock,
        mock_interest_address: MagicMock,
        mock_fee_address: MagicMock,
    ):
        balance_def = {
            "FEES": ["UNPAID"],
            "INTEREST": ["BILLED"],
            "PRINCIPAL": ["CHARGED"],
        }  # : [states]
        txn_type_map: dict[str, Optional[list[str]]] = {
            "PURCHASE": None,
            "CASH_ADVANCE": None,
            "TRANSFER": None,
        }  # txn_type:txn_ref
        fee_types = ["ANNUAL_FEE", "DISPUTE_FEE"]

        mock_principal_address.side_effect = [
            "PURCHASE_CHARGED",
            "CASH_ADVANCE_CHARGED",
            "TRANSFER_CHARGED",
        ]
        mock_interest_address.side_effect = [
            "PURCHASE_INTEREST_BILLED",
            "CASH_ADVANCE_INTEREST_BILLED",
            "TRANSFER_INTEREST_BILLED",
            "ANNUAL_FEE_INTEREST_BILLED",
            "DISPUTE_FEE_INTEREST_BILLED",
        ]
        mock_fee_address.side_effect = [
            "ANNUAL_FEES_UNPAID",
            "DISPUTE_FEES_UNPAID",
        ]

        # expected = CASH_ADVANCE_CHARGED + PURCHASE_INTEREST_BILLED + DISPUTE_FEES_UNPAID
        expected_result = Decimal("1000010010")  # 10 + 10000 + 1000000000

        results = credit_card._calculate_aggregate_balance(
            balances=self.balances,
            denomination=sentinel.denomination,
            fee_types=fee_types,
            balance_def=balance_def,
            include_deposit=False,
            txn_type_map=txn_type_map,
        )

        self.assertEqual(results, expected_result)


@patch.object(credit_card, "_calculate_aggregate_balance")
class GetAvailableBalance(CreditCardTestBase):
    def test_available_balance_returned(
        self,
        mock_calculate_aggregate_balance: MagicMock,
    ):
        balances = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ): Balance(net=Decimal("100")),
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.PENDING_OUT,
                ): Balance(net=Decimal("30")),
            },
        )

        mock_calculate_aggregate_balance.return_value = Decimal("5")  # charged interest

        expected_result = Decimal("675")  # = 800 - (100 + 30) + 5

        result = credit_card._get_available_balance(
            credit_limit=Decimal("800"),
            balances=balances,
            txn_types=sentinel.txn_types,
            denomination=sentinel.denomination,
        )

        self.assertEqual(result, expected_result)
        mock_calculate_aggregate_balance.assert_called_once_with(
            balances=balances,
            denomination=sentinel.denomination,
            txn_type_map=sentinel.txn_types,
            fee_types=[],
            balance_def={credit_card.INTEREST: [credit_card.CHARGED]},
            include_deposit=False,
        )


class PrincipalAddressTest(CreditCardTestBase):
    txn_type = "TXN_TYPE"
    txn_type_status = "STATUS"

    def test_principal_address_without_txn_ref(self):
        expected_result = f"{self.txn_type}_{self.txn_type_status}"

        results = credit_card._principal_address(
            txn_type=self.txn_type,
            txn_type_status=self.txn_type_status,
        )

        self.assertEqual(results, expected_result)

    def test_principal_address_with_txn_ref(self):
        expected_result = f"{self.txn_type}_REF_{self.txn_type_status}"

        results = credit_card._principal_address(
            txn_type=self.txn_type,
            txn_type_status=self.txn_type_status,
            txn_ref="REF",
        )

        self.assertEqual(results, expected_result)


class InterestAddressTest(CreditCardTestBase):
    txn_type = "TXN_TYPE"
    txn_ref = "TXN_REF"
    interest_status = "INTEREST_STATUS"

    def test_interest_address_without_txn_ref(self):
        expected_result = f"{self.txn_type}_{credit_card.INTEREST}_{self.interest_status}"

        results = credit_card._interest_address(
            txn_type=self.txn_type,
            interest_status=self.interest_status,
        )

        self.assertEqual(results, expected_result)

    def test_interest_address_with_txn_ref(self):
        expected_result = (
            f"{self.txn_type}_{self.txn_ref}_{credit_card.INTEREST}_{self.interest_status}"
        )

        results = credit_card._interest_address(
            txn_type=self.txn_type,
            interest_status=self.interest_status,
            txn_ref=self.txn_ref,
        )

        self.assertEqual(results, expected_result)

    def test_interest_address_with_txn_ref_and_interest_free_txn_type(self):
        expected_result = (
            f"{self.txn_type}_{self.txn_ref}_"
            + credit_card.INTEREST_FREE_PERIOD
            + f"_{credit_card.INTEREST}_{self.interest_status}"
        )

        results = credit_card._interest_address(
            txn_type=f"{self.txn_type}_{credit_card.INTEREST_FREE_PERIOD}",
            interest_status=self.interest_status,
            txn_ref=self.txn_ref,
        )

        self.assertEqual(results, expected_result)


class GetTxnTypeAndRefFromAddressTest(CreditCardTestBase):
    def test_stem_in_base_txn_types(self):
        expected_result = ("CASH_PURCHASE", None)

        result = credit_card._get_txn_type_and_ref_debit_address(
            address="CASH_PURCHASE_INTEREST_UNCHARGED",
            base_txn_types=["CASH_PURCHASE"],
            address_type="INTEREST_UNCHARGED",
        )

        self.assertEqual(result, expected_result)

    def test_stem_starts_with_base_txn_types(self):
        expected_result = ("BALANCE_TRANSFER", "REF1")

        result = credit_card._get_txn_type_and_ref_debit_address(
            address="BALANCE_TRANSFER_REF1_INTEREST_CHARGED",
            base_txn_types=["BALANCE_TRANSFER"],
            address_type="INTEREST_CHARGED",
        )

        self.assertEqual(result, expected_result)

    def test_stem_not_in_base_txn_types(self):
        expected_result = ("CASH_PURCHASE_I", None)

        result = credit_card._get_txn_type_and_ref_debit_address(
            address="CASH_PURCHASE_INTEREST_UNCHARGED",
            base_txn_types=["BALANCE_TRANSFER"],
            address_type="INTEREST_CHARGED",
        )

        self.assertEqual(result, expected_result)


@patch.object(credit_card, "_adjust_aggregate_balances")
@patch.object(credit_card, "_bill_charged_interest")
@patch.object(credit_card, "_get_supported_fee_types")
@patch.object(credit_card, "_rebalance_balance_buckets")
@patch.object(credit_card, "_fee_address")
@patch.object(credit_card, "_principal_address")
class BillChargedTransactionsAndBankChargesTest(CreditCardTestBase):
    def test_with_principal_and_fee_addresses(
        self,
        mock_principal_address: MagicMock,
        mock_fee_address: MagicMock,
        mock_rebalance_balance_buckets: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_bill_charged_interest: MagicMock,
        mock_adjust_aggregate_balances: MagicMock,
    ):
        # construct values
        principal_address_postings = [SentinelCustomInstruction("principal_address")]
        fee_address_postings = [SentinelCustomInstruction("fee_address")]
        bill_charged_interest_postings = [SentinelCustomInstruction("bill_charged_interest")]
        adjust_aggregate_balances_postings = [SentinelCustomInstruction("adjust_aggregate_balance")]
        supported_txn_types: dict[str, Optional[list[str]]] = {"PURCHASE": None}
        supported_fee_types = ["ANNUAL_FEE"]

        expected_result = [
            *principal_address_postings,
            *fee_address_postings,
            *bill_charged_interest_postings,
            *adjust_aggregate_balances_postings,
        ]

        # construct mocks
        mock_principal_address.side_effect = ["PURCHASE_CHARGED", "PURCHASE_BILLED"]
        mock_get_supported_fee_types.return_value = supported_fee_types
        mock_fee_address.side_effect = ["ANNUAL_FEES_CHARGED", "ANNUAL_FEES_BILLED"]
        mock_rebalance_balance_buckets.side_effect = [
            (
                sentinel._,
                principal_address_postings,
            ),
            (
                sentinel._,
                fee_address_postings,
            ),
        ]
        mock_bill_charged_interest.return_value = bill_charged_interest_postings
        mock_adjust_aggregate_balances.return_value = adjust_aggregate_balances_postings

        # run function
        result = credit_card._bill_charged_txns_and_bank_charges(
            vault=sentinel.vault,
            supported_txn_types=supported_txn_types,
            denomination=self.default_denomination,
            in_flight_balances=sentinel.in_flight_balances,
            credit_limit=sentinel.credit_limit,
        )
        self.assertEqual(expected_result, result)

        # assert calls
        mock_principal_address.assert_has_calls(
            calls=[
                call("PURCHASE", "CHARGED", txn_ref=""),
                call("PURCHASE", "BILLED", txn_ref=""),
            ]
        )
        mock_get_supported_fee_types.assert_called_once_with(
            sentinel.vault,
            supported_txn_types,
        )
        mock_fee_address.assert_has_calls(
            calls=[
                call(fee_type="ANNUAL_FEE", fee_status="CHARGED"),
                call(fee_type="ANNUAL_FEE", fee_status="BILLED"),
            ]
        )
        mock_rebalance_balance_buckets.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.vault,
                    in_flight_balances=sentinel.in_flight_balances,
                    debit_address="PURCHASE_CHARGED",
                    credit_address="PURCHASE_BILLED",
                    denomination=self.default_denomination,
                ),
                call(
                    vault=sentinel.vault,
                    in_flight_balances=sentinel.in_flight_balances,
                    debit_address="ANNUAL_FEES_CHARGED",
                    credit_address="ANNUAL_FEES_BILLED",
                    denomination=self.default_denomination,
                ),
            ]
        )
        mock_bill_charged_interest.assert_called_once_with(
            sentinel.vault,
            supported_fee_types,
            supported_txn_types,
            self.default_denomination,
            sentinel.in_flight_balances,
        )
        mock_adjust_aggregate_balances.assert_called_once_with(
            sentinel.vault,
            self.default_denomination,
            sentinel.in_flight_balances,
            outstanding=False,
            full_outstanding=False,
            credit_limit=sentinel.credit_limit,
        )


@patch.object(credit_card, "_interest_address")
@patch.object(credit_card, "_make_internal_address_transfer")
class MakeAccrualPostingTest(CreditCardTestBase):
    def test_make_accrual_posting(
        self,
        mock_make_internal_address_transfer: MagicMock,
        mock_interest_address: MagicMock,
    ):
        # construct mocks
        mock_make_internal_address_transfer.return_value = [
            SentinelCustomInstruction("internal_address_transfer_instructions")
        ]
        mock_interest_address.return_value = "PURCHASE_UNCHARGED"

        # run function
        result = credit_card._make_accrual_posting(
            vault=sentinel.vault,
            accrual_amount=Decimal("1"),
            denomination=self.default_denomination,
            stem="PURCHASE",
        )
        self.assertEqual(mock_make_internal_address_transfer.return_value, result)

        # assert calls
        mock_interest_address.assert_called_once_with("PURCHASE", "UNCHARGED", accrual_type=None)
        mock_make_internal_address_transfer.assert_called_once_with(
            amount=abs(Decimal("1")),
            denomination=self.default_denomination,
            credit_internal=True,
            custom_address=mock_interest_address.return_value,
            instruction_details=None,
            vault=sentinel.vault,
        )


class CalculateAccrualsAndCreateInstructionsTest(CreditCardTestBase):
    @patch.object(credit_card.utils, "round_decimal")
    @patch.object(credit_card, "yearly_to_daily_rate")
    def test_zero_accrual_amount(
        self,
        mock_yearly_to_daily_rate: MagicMock,
        mock_round_decimal: MagicMock,
    ):
        # construct values
        balances_to_accrue_on = {("CHARGE_TYPE", "SUB_TYPE", "ACCRUAL_TYPE"): {"": Decimal("0")}}
        base_interest_rates = {"sub_type": "0.365"}
        instructions: list[CustomInstruction] = []
        txn_types_to_charge_interest_from_txn_date: list[str] = []
        txn_types_in_interest_free_period: dict[str, list[str]] = {}

        # construct mocks
        mock_yearly_to_daily_rate.return_value = Decimal("0.001")
        mock_round_decimal.return_value = Decimal("0.00")

        # run function
        result = credit_card._calculate_accruals_and_create_instructions(
            vault=sentinel.vault,
            balances_to_accrue_on=balances_to_accrue_on,
            denomination=self.default_denomination,
            base_interest_rates=base_interest_rates,
            instructions=instructions,
            leap_year=False,
            is_revolver=False,
            txn_types_to_charge_interest_from_txn_date=txn_types_to_charge_interest_from_txn_date,
            txn_types_in_interest_free_period=txn_types_in_interest_free_period,
        )
        self.assertDictEqual({}, result)

        # assert calls
        mock_yearly_to_daily_rate.assert_called_once_with(Decimal("0.365"), False)
        mock_round_decimal.assert_called_once_with(
            Decimal("0.001") * Decimal("0.00"),
            decimal_places=2,
        )

    @patch.object(credit_card, "_set_accruals_by_sub_type")
    @patch.object(credit_card, "_is_txn_type_in_interest_free_period")
    @patch.object(credit_card.utils, "round_decimal")
    @patch.object(credit_card, "yearly_to_daily_rate")
    def test_is_txn_type_in_interest_free_period_false(
        self,
        mock_yearly_to_daily_rate: MagicMock,
        mock_round_decimal: MagicMock,
        mock_is_txn_type_in_interest_free_period: MagicMock,
        mock_set_accruals_by_sub_type: MagicMock,
    ):
        # construct values
        balances_to_accrue_on = {
            ("INTEREST", "CASH_ADVANCE", "PRE_SCOD"): {"": Decimal("10000")},
        }
        base_interest_rates = {"cash_advance": "0.365"}
        instructions: list[CustomInstruction] = []
        txn_types_to_charge_interest_from_txn_date: list[str] = ["cash_advance"]
        txn_types_in_interest_free_period: dict[str, list[str]] = {}

        # expected result
        expected_result = {("INTEREST", "CASH_ADVANCE", "PRE_SCOD"): {"": Decimal("10.00")}}

        # construct mocks
        mock_yearly_to_daily_rate.return_value = Decimal("0.001")
        mock_round_decimal.return_value = Decimal("10.00")
        mock_is_txn_type_in_interest_free_period.return_value = False

        def _set_accruals_by_sub_type_side_effect(
            interest_by_charge_sub_and_accrual_type,
            charge_type,
            sub_type,
            accrual_amount,
            ref,
            accrual_type,
        ):
            interest_by_charge_sub_and_accrual_type.update(expected_result)

        mock_set_accruals_by_sub_type.side_effect = _set_accruals_by_sub_type_side_effect

        # run function
        result = credit_card._calculate_accruals_and_create_instructions(
            vault=sentinel.vault,
            balances_to_accrue_on=balances_to_accrue_on,
            denomination=self.default_denomination,
            base_interest_rates=base_interest_rates,
            instructions=instructions,
            leap_year=False,
            is_revolver=False,
            txn_types_to_charge_interest_from_txn_date=txn_types_to_charge_interest_from_txn_date,
            txn_types_in_interest_free_period=txn_types_in_interest_free_period,
        )
        self.assertDictEqual(expected_result, result)

        # assert calls
        mock_yearly_to_daily_rate.assert_called_once_with(Decimal("0.365"), False)
        mock_round_decimal.assert_called_once_with(
            Decimal("0.001") * Decimal("10000.00"),
            decimal_places=2,
        )
        mock_is_txn_type_in_interest_free_period.assert_called_once_with(
            txn_types_in_interest_free_period, "CASH_ADVANCE", ""
        )
        mock_set_accruals_by_sub_type.assert_called_once_with(
            ANY,
            charge_type="INTEREST",
            sub_type="CASH_ADVANCE",
            accrual_amount=Decimal("10"),
            ref="",
            accrual_type="PRE_SCOD",
        )

    @patch.object(credit_card, "_make_accrual_posting")
    @patch.object(credit_card, "_is_txn_type_in_interest_free_period")
    @patch.object(credit_card.utils, "round_decimal")
    @patch.object(credit_card, "yearly_to_daily_rate")
    def test_is_txn_type_in_interest_free_period_true(
        self,
        mock_yearly_to_daily_rate: MagicMock,
        mock_round_decimal: MagicMock,
        mock_is_txn_type_in_interest_free_period: MagicMock,
        mock_make_accrual_posting: MagicMock,
    ):
        # construct values
        balances_to_accrue_on = {
            ("INTEREST", "PURCHASE", "PRE_SCOD"): {"": Decimal("10000")},
        }
        base_interest_rates = {"purchase": "0.365"}
        instructions: list[CustomInstruction] = []
        txn_types_to_charge_interest_from_txn_date: list[str] = []
        txn_types_in_interest_free_period: dict[str, list[str]] = {"purchase": []}
        instruction_details = {
            "description": "Daily interest accrued at 0.1000000%% on balance"
            " of 10000.00, for transaction type PURCHASE_INTEREST_FREE_PERIOD_PRE_SCOD"
        }

        # construct mocks
        mock_yearly_to_daily_rate.return_value = Decimal("0.001")
        mock_round_decimal.return_value = Decimal("10.00")
        mock_is_txn_type_in_interest_free_period.return_value = True
        mock_make_accrual_posting.return_value = [SentinelCustomInstruction("accruals")]

        # run function
        result = credit_card._calculate_accruals_and_create_instructions(
            vault=sentinel.vault,
            balances_to_accrue_on=balances_to_accrue_on,
            denomination=self.default_denomination,
            base_interest_rates=base_interest_rates,
            instructions=instructions,
            leap_year=False,
            is_revolver=False,
            txn_types_to_charge_interest_from_txn_date=txn_types_to_charge_interest_from_txn_date,
            txn_types_in_interest_free_period=txn_types_in_interest_free_period,
        )
        self.assertDictEqual({}, result)
        self.assertEqual([SentinelCustomInstruction("accruals")], instructions)

        # assert calls
        mock_yearly_to_daily_rate.assert_called_once_with(Decimal("0.365"), False)
        mock_round_decimal.assert_called_once_with(
            Decimal("0.001") * Decimal("10000.00"),
            decimal_places=2,
        )
        mock_is_txn_type_in_interest_free_period.assert_called_once_with(
            txn_types_in_interest_free_period, "PURCHASE", ""
        )
        mock_make_accrual_posting.assert_called_once_with(
            sentinel.vault,
            Decimal("10.00"),
            self.default_denomination,
            "PURCHASE_INTEREST_FREE_PERIOD",
            instruction_details=instruction_details,
            accrual_type="PRE_SCOD",
        )


@patch.object(credit_card, "_get_previous_scod")
class IsBetweenPDDAndSCODTest(CreditCardTestBase):
    def test_is_between_pdd_and_scod(
        self,
        mock_get_previous_scod: MagicMock,
    ):
        mock_get_previous_scod.return_value = (
            DEFAULT_DATETIME,
            DEFAULT_DATETIME - relativedelta(days=1),
        )
        result = credit_card._is_between_pdd_and_scod(
            sentinel.vault,
            payment_due_period=21,
            account_creation_datetime=DEFAULT_DATETIME,
            current_datetime=DEFAULT_DATETIME + relativedelta(days=25),
        )

        self.assertTrue(result)

    def test_is_not_between_pdd_and_scod_prev_scod_equals_creation_dt(
        self,
        mock_get_previous_scod: MagicMock,
    ):
        mock_get_previous_scod.return_value = (DEFAULT_DATETIME, DEFAULT_DATETIME)
        result = credit_card._is_between_pdd_and_scod(
            sentinel.vault,
            payment_due_period=21,
            account_creation_datetime=DEFAULT_DATETIME,
            current_datetime=DEFAULT_DATETIME,
        )

        self.assertFalse(result)

    def test_is_not_between_pdd_and_scod_is_before_next_pdd(
        self,
        mock_get_previous_scod: MagicMock,
    ):
        mock_get_previous_scod.return_value = (
            DEFAULT_DATETIME,
            DEFAULT_DATETIME - relativedelta(days=1),
        )
        result = credit_card._is_between_pdd_and_scod(
            sentinel.vault,
            payment_due_period=21,
            account_creation_datetime=DEFAULT_DATETIME,
            current_datetime=DEFAULT_DATETIME + relativedelta(days=5),
        )

        self.assertFalse(result)


@patch.object(credit_card, "_get_supported_txn_types")
@patch.object(credit_card.utils, "get_parameter")
class GetTxnTypeAndRefFromPostingTest(CreditCardTestBase):
    def test_get_txn_type_and_ref_with_map(
        self, mock_get_parameter: MagicMock, mock_get_supported_txn_types: MagicMock
    ):
        expected_result = ("PURCHASE", None)

        result = credit_card._get_txn_type_and_ref_from_posting(
            sentinel.vault,
            instruction_details={"transaction_code": "aaa"},
            effective_datetime=DEFAULT_DATETIME,
            supported_txn_types={"test": ["test"]},
            txn_code_to_type_map={
                "": "cash_advance",
                "01": "purchase",
            },
            upper_case_type=True,
        )

        self.assertEqual(result, expected_result)
        mock_get_parameter.assert_not_called()
        mock_get_supported_txn_types.assert_not_called()

    def test_no_txn_code_to_type_map(
        self, mock_get_parameter: MagicMock, mock_get_supported_txn_types: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "transaction_code_to_type_map": {
                    "": "cash_advance",
                    "01": "purchase",
                }
            }
        )

        expected_result = ("PURCHASE", None)

        result = credit_card._get_txn_type_and_ref_from_posting(
            sentinel.vault,
            instruction_details={"transaction_code": "aaa"},
            effective_datetime=DEFAULT_DATETIME,
            supported_txn_types={"test": ["test"]},
            upper_case_type=True,
        )

        self.assertEqual(result, expected_result)
        mock_get_supported_txn_types.assert_not_called()

    def test_no_supported_txn_types(
        self, mock_get_parameter: MagicMock, mock_get_supported_txn_types: MagicMock
    ):
        mock_get_supported_txn_types.return_value = {"test": ["test"]}

        expected_result = ("PURCHASE", None)

        result = credit_card._get_txn_type_and_ref_from_posting(
            sentinel.vault,
            instruction_details={"transaction_code": "aaa"},
            effective_datetime=DEFAULT_DATETIME,
            txn_code_to_type_map={
                "": "cash_advance",
                "01": "purchase",
            },
            upper_case_type=True,
        )

        self.assertEqual(result, expected_result)
        mock_get_parameter.assert_not_called()

    def test_get_txn_type_and_ref_from_posting_with_ref(
        self, mock_get_parameter: MagicMock, mock_get_supported_txn_types: MagicMock
    ):
        expected_result = ("PURCHASE", "BBB")

        result = credit_card._get_txn_type_and_ref_from_posting(
            sentinel.vault,
            instruction_details={"transaction_code": "aaa", "transaction_ref": "bbb"},
            effective_datetime=DEFAULT_DATETIME,
            supported_txn_types={"test": ["test"]},
            txn_code_to_type_map={
                "": "cash_advance",
                "01": "purchase",
            },
            upper_case_type=True,
        )

        self.assertEqual(result, expected_result)
        mock_get_parameter.assert_not_called()
        mock_get_supported_txn_types.assert_not_called()


class GetUnsettledAmountTest(CreditCardTestBase):
    def test_get_unsettled_amount(self):
        test_posting_instructions = [
            self.outbound_auth(
                client_transaction_id="TEST_ID",
                amount=Decimal("100"),
                denomination=self.default_denomination,
                target_account_id=ACCOUNT_ID,
                internal_account_id="1",
            ),
            self.settle_outbound_auth(
                unsettled_amount=Decimal("15"),
                client_transaction_id="TEST_ID",
            ),
            self.settle_outbound_auth(
                unsettled_amount=Decimal("7"), client_transaction_id="TEST_ID", final=True
            ),
        ]

        expected_result = Decimal("85")
        result = credit_card._get_unsettled_amount(
            denomination=self.default_denomination,
            client_transaction=ClientTransaction(
                client_transaction_id="TEST_ID",
                account_id=ACCOUNT_ID,
                posting_instructions=test_posting_instructions,
            ),
        )

        self.assertEqual(result, expected_result)


class ProcessStatementCutOffTest(CreditCardTestBase):
    def setUp(self) -> None:
        self.effective_date = datetime(2019, 1, 1, 1, 2, 3, 4, tzinfo=ZoneInfo("UTC"))

        self.common_get_param_return_values: dict = {
            "denomination": sentinel.denomination,
            "credit_limit": sentinel.credit_limit,
            "transaction_types": {},
        }
        patch_get_parameter = patch.object(credit_card.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values},
        )

        patch_get_supported_txn_types = patch.object(credit_card, "_get_supported_txn_types")
        self.mock_get_supported_txn_types = patch_get_supported_txn_types.start()
        self.mock_get_supported_txn_types.return_value = sentinel.supported_txn_types

        patch_get_supported_fee_types = patch.object(credit_card, "_get_supported_fee_types")
        self.mock_get_supported_fee_types = patch_get_supported_fee_types.start()
        self.mock_get_supported_fee_types.return_value = sentinel.supported_fee_types

        patch_is_txn_interest_accrual_from_txn_day = patch.object(
            credit_card, "_is_txn_interest_accrual_from_txn_day"
        )
        self.mock_is_txn_interest_accrual_from_txn_day = (
            patch_is_txn_interest_accrual_from_txn_day.start()
        )
        self.mock_is_txn_interest_accrual_from_txn_day.return_value = True

        patch_charge_overlimit_fee = patch.object(credit_card, "_charge_overlimit_fee")
        self.mock_charge_overlimit_fee = patch_charge_overlimit_fee.start()
        # keyed by scod_cut_off_datetime
        self.mock_charge_overlimit_fee.return_value = [
            SentinelCustomInstruction("_charge_overlimit_fee")
        ]

        patch_bill_charged_txns_and_bank_charges = patch.object(
            credit_card, "_bill_charged_txns_and_bank_charges"
        )
        self.mock_bill_charged_txns_and_bank_charges = (
            patch_bill_charged_txns_and_bank_charges.start()
        )
        # keyed by scod_effective_dt
        self.mock_bill_charged_txns_and_bank_charges.return_value = [
            SentinelCustomInstruction("_bill_charged_txns_and_bank_charges")
        ]

        patch_adjust_interest_uncharged_balances = patch.object(
            credit_card, "_adjust_interest_uncharged_balances"
        )
        self.mock_adjust_interest_uncharged_balances = (
            patch_adjust_interest_uncharged_balances.start()
        )
        # keyed by scod_effective_dt
        self.mock_adjust_interest_uncharged_balances.return_value = [
            SentinelCustomInstruction("_adjust_interest_uncharged_balances")
        ]

        patch_get_outstanding_statement_amount = patch.object(
            credit_card, "_get_outstanding_statement_amount"
        )
        self.mock_get_outstanding_statement_amount = patch_get_outstanding_statement_amount.start()
        self.mock_get_outstanding_statement_amount.return_value = Decimal("50")

        patch_calculate_mad = patch.object(credit_card, "_calculate_mad")
        self.mock_calculate_mad = patch_calculate_mad.start()
        self.mock_calculate_mad.return_value = Decimal("100")

        patch_is_flag_in_list_applied = patch.object(credit_card.utils, "is_flag_in_list_applied")
        self.mock_is_flag_in_list_applied = patch_is_flag_in_list_applied.start()
        self.mock_is_flag_in_list_applied.return_value = sentinel.true

        patch_update_info_balances = patch.object(credit_card, "_update_info_balances")
        self.mock_update_info_balances = patch_update_info_balances.start()
        # keyed by scod_effective_dt
        self.mock_update_info_balances.return_value = [
            SentinelCustomInstruction("_update_info_balances")
        ]

        def _handle_live_balance_changes_side_effect(
            vault,
            denomination,
            cut_off_datetime,
            instructions_timeseries,
        ):
            instructions_timeseries[cut_off_datetime].extend(
                [SentinelCustomInstruction("_handle_live_balance_changes")]
            )

        patch_handle_live_balance_changes = patch.object(
            credit_card, "_handle_live_balance_changes"
        )
        self.mock_handle_live_balance_changes = patch_handle_live_balance_changes.start()
        self.mock_handle_live_balance_changes.side_effect = _handle_live_balance_changes_side_effect

        patch_create_statement_notification = patch.object(
            credit_card, "_create_statement_notification"
        )
        self.mock_create_statement_notification = patch_create_statement_notification.start()
        self.mock_create_statement_notification.return_value = SentinelAccountNotificationDirective(
            "statement_notification"
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_accrue_interest_from_txn_day_and_is_not_final(self):
        # is_final = False so update datetimes
        scod_effective_dt = datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC"))
        scod_cut_off_datetime = datetime(2018, 12, 31, 23, 59, 59, 999999, tzinfo=ZoneInfo("UTC"))

        # construct mocks
        mock_vault = self.create_mock(balances_interval_fetchers_mapping={})

        # construct expected result
        expected_notifications = [SentinelAccountNotificationDirective("statement_notification")]
        expected_posting_directives = [
            PostingInstructionsDirective(
                posting_instructions=[
                    SentinelCustomInstruction("_charge_overlimit_fee"),
                    SentinelCustomInstruction("_handle_live_balance_changes"),
                ],
                client_batch_id="SCOD_0-MOCK_HOOK",
                value_datetime=scod_cut_off_datetime,  # scod_cut_off
            ),
            PostingInstructionsDirective(
                posting_instructions=[
                    SentinelCustomInstruction("_bill_charged_txns_and_bank_charges"),
                    SentinelCustomInstruction("_adjust_interest_uncharged_balances"),
                    SentinelCustomInstruction("_update_info_balances"),
                ],
                client_batch_id="SCOD_1-MOCK_HOOK",
                value_datetime=scod_effective_dt,  # scod_effective
            ),
        ]

        # run function
        result_notifications, result_posting_directives = credit_card._process_statement_cut_off(
            vault=mock_vault,
            effective_datetime=self.effective_date,
            in_flight_balances=sentinel.inflight_balances,
            is_final=False,
        )
        self.assertListEqual(result_notifications, expected_notifications)
        self.assertListEqual(result_posting_directives, expected_posting_directives)

        self.mock_charge_overlimit_fee.assert_called_once_with(
            mock_vault,
            sentinel.inflight_balances,
            sentinel.denomination,
            sentinel.supported_txn_types,
            sentinel.credit_limit,
        )
        self.mock_bill_charged_txns_and_bank_charges.assert_called_once_with(
            mock_vault,
            sentinel.supported_txn_types,
            sentinel.denomination,
            sentinel.inflight_balances,
            sentinel.credit_limit,
        )
        self.mock_adjust_interest_uncharged_balances.assert_called_once_with(
            mock_vault,
            sentinel.supported_txn_types,
            [],  # txn_types_to_charge_interest_from_txn_date
            sentinel.denomination,
            sentinel.inflight_balances,
        )
        self.mock_get_outstanding_statement_amount.assert_called_once_with(
            sentinel.inflight_balances,
            sentinel.denomination,
            sentinel.supported_fee_types,
            sentinel.supported_txn_types,
        )
        self.mock_calculate_mad.assert_called_once_with(
            mock_vault,
            sentinel.inflight_balances,
            sentinel.denomination,
            sentinel.supported_txn_types,
            scod_effective_dt,
            Decimal("50"),
            mad_eq_statement=sentinel.true,
        )
        self.mock_update_info_balances.assert_called_once_with(
            mock_vault,
            sentinel.inflight_balances,
            sentinel.denomination,
            Decimal("50"),
            Decimal("100"),
        )
        self.mock_handle_live_balance_changes.assert_called_once_with(
            mock_vault, sentinel.denomination, scod_cut_off_datetime, ANY
        )
        self.mock_create_statement_notification.assert_called_once_with(
            mock_vault, scod_effective_dt, Decimal("50"), Decimal("100"), False
        )

    def test_is_final_and_in_flight_balances_not_provided(self):
        # construct mocks
        bif_mapping = {
            credit_card.STATEMENT_CUTOFF_TO_LIVE_BALANCES_BIF_ID: defaultdict(
                None,
                {
                    DEFAULT_COORDINATE: self.construct_balance_timeseries(
                        dt=self.effective_date,
                        net=Decimal("10"),
                    )
                },
            )
        }
        inflight_balances = {
            DEFAULT_COORDINATE: Balance(credit=Decimal(0), debit=Decimal(10), net=Decimal(10))
        }
        mock_vault = self.create_mock(balances_interval_fetchers_mapping=bif_mapping)

        # construct expected result
        expected_notifications = [SentinelAccountNotificationDirective("statement_notification")]
        expected_posting_directives = [
            PostingInstructionsDirective(
                posting_instructions=[
                    SentinelCustomInstruction("_charge_overlimit_fee"),
                    SentinelCustomInstruction("_bill_charged_txns_and_bank_charges"),
                    SentinelCustomInstruction("_update_info_balances"),
                ],
                client_batch_id="SCOD_0-MOCK_HOOK",
                value_datetime=self.effective_date,
            ),
        ]

        # run function
        result_notifications, result_posting_directives = credit_card._process_statement_cut_off(
            vault=mock_vault,
            effective_datetime=self.effective_date,
            in_flight_balances=None,
            is_final=True,
        )
        self.assertListEqual(result_notifications, expected_notifications)
        self.assertListEqual(result_posting_directives, expected_posting_directives)

        self.mock_charge_overlimit_fee.assert_called_once_with(
            mock_vault,
            inflight_balances,
            sentinel.denomination,
            sentinel.supported_txn_types,
            sentinel.credit_limit,
        )
        self.mock_bill_charged_txns_and_bank_charges.assert_called_once_with(
            mock_vault,
            sentinel.supported_txn_types,
            sentinel.denomination,
            inflight_balances,
            sentinel.credit_limit,
        )
        self.mock_adjust_interest_uncharged_balances.assert_not_called()
        self.mock_get_outstanding_statement_amount.assert_called_once_with(
            inflight_balances,
            sentinel.denomination,
            sentinel.supported_fee_types,
            sentinel.supported_txn_types,
        )
        self.mock_calculate_mad.assert_called_once_with(
            mock_vault,
            inflight_balances,
            sentinel.denomination,
            sentinel.supported_txn_types,
            self.effective_date,
            Decimal("50"),
            mad_eq_statement=sentinel.true,
        )
        self.mock_update_info_balances.assert_called_once_with(
            mock_vault,
            inflight_balances,
            sentinel.denomination,
            Decimal("50"),
            Decimal("100"),
        )
        self.mock_handle_live_balance_changes.assert_not_called()
        self.mock_create_statement_notification.assert_called_once_with(
            mock_vault, self.effective_date, Decimal("50"), Decimal("100"), True
        )


class ProcessWriteOffTest(CreditCardTestBase):
    def setUp(self) -> None:
        self.common_get_param_return_values: dict = {
            "principal_write_off_internal_account": sentinel.principal_write_off_internal_account,
            "interest_write_off_internal_account": sentinel.interest_write_off_internal_account,
            "credit_limit": sentinel.credit_limit,
        }
        patch_get_parameter = patch.object(credit_card.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values},
        )

        patch_get_supported_txn_types = patch.object(credit_card, "_get_supported_txn_types")
        self.mock_get_supported_txn_types = patch_get_supported_txn_types.start()
        self.mock_get_supported_txn_types.return_value = sentinel.supported_txn_types

        patch_get_supported_fee_types = patch.object(credit_card, "_get_supported_fee_types")
        self.mock_get_supported_fee_types = patch_get_supported_fee_types.start()
        self.mock_get_supported_fee_types.return_value = sentinel.supported_fee_types

        patch_calculate_aggregate_balance = patch.object(
            credit_card, "_calculate_aggregate_balance"
        )
        self.mock_calculate_aggregate_balance = patch_calculate_aggregate_balance.start()
        self.mock_calculate_aggregate_balance.side_effect = [
            Decimal("1"),  # finance principal
            Decimal("2"),  # interest
        ]

        patch_gl_posting_metadata = patch.object(credit_card, "_gl_posting_metadata")
        self.mock_gl_posting_metadata = patch_gl_posting_metadata.start()
        self.mock_gl_posting_metadata.return_value = sentinel.instruction_details

        patch_create_custom_instructions = patch.object(credit_card, "_create_custom_instructions")
        self.mock_create_custom_instructions = patch_create_custom_instructions.start()

        patch_process_repayment = patch.object(credit_card, "_process_repayment")
        self.mock_process_repayment = patch_process_repayment.start()
        self.mock_process_repayment.return_value = [
            SentinelCustomInstruction("process_repayment")
        ], sentinel._

        patch_adjust_aggregate_balances = patch.object(credit_card, "_adjust_aggregate_balances")
        self.mock_adjust_aggregate_balances = patch_adjust_aggregate_balances.start()
        self.mock_adjust_aggregate_balances.return_value = [
            SentinelCustomInstruction("update_aggregate_balances")
        ]

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_no_process_repayment_instructions(self):
        # construct mocks
        mock_vault = self.create_mock()
        # since we are using SentinelCustomInstruction for _create_custom_instructions,
        # the outcome of `posting.balances(vault.account_id, vault.tside)` will
        # be an empty dict, and hence _process_repayment is not called
        self.mock_create_custom_instructions.side_effect = [
            [SentinelCustomInstruction("finance_principal")],
            [SentinelCustomInstruction("interest")],
        ]

        # construct expected result
        expected_result = [
            SentinelCustomInstruction("finance_principal"),
            SentinelCustomInstruction("interest"),
            SentinelCustomInstruction("update_aggregate_balances"),
        ]

        # run function
        result = credit_card._process_write_off(
            vault=mock_vault,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertListEqual(result, expected_result)
        self.mock_create_custom_instructions.assert_has_calls(
            calls=[
                call(
                    mock_vault,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    debit_account_id=sentinel.principal_write_off_internal_account,
                    credit_account_id=mock_vault.account_id,
                    instruction_details=sentinel.instruction_details,
                ),
                call(
                    mock_vault,
                    amount=Decimal("2"),
                    denomination=sentinel.denomination,
                    debit_account_id=sentinel.interest_write_off_internal_account,
                    credit_account_id=mock_vault.account_id,
                    instruction_details=sentinel.instruction_details,
                ),
            ]
        )
        self.mock_process_repayment.assert_not_called()
        self.mock_adjust_aggregate_balances.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            sentinel.in_flight_balances,
            DEFAULT_DATETIME,
            credit_limit=sentinel.credit_limit,
        )

    def test_include_process_repayment_instructions(self):
        # construct mocks
        mock_vault = self.create_mock()
        # build a non-sentinel CustomInstruction so that
        # `posting.balances(vault.account_id, vault.tside)` evaluates to a
        # non-empty dictionary and _process_repayment instructions are included
        interest_instruction = CustomInstruction(
            postings=[
                Posting(
                    credit=True,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_address=sentinel.account_address,
                    account_id=mock_vault.account_id,
                    asset=sentinel.asset,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_address=sentinel.account_address,
                    account_id=mock_vault.account_id,
                    asset=sentinel.asset,
                    phase=Phase.COMMITTED,
                ),
            ],
        )
        self.mock_create_custom_instructions.side_effect = [
            [SentinelCustomInstruction("finance_principal")],
            [interest_instruction],
        ]

        # construct expected result
        expected_result = [
            SentinelCustomInstruction("finance_principal"),
            interest_instruction,
            SentinelCustomInstruction("process_repayment"),
            SentinelCustomInstruction("update_aggregate_balances"),
        ]

        # run function
        result = credit_card._process_write_off(
            vault=mock_vault,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertListEqual(result, expected_result)
        self.mock_create_custom_instructions.assert_has_calls(
            calls=[
                call(
                    mock_vault,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    debit_account_id=sentinel.principal_write_off_internal_account,
                    credit_account_id=mock_vault.account_id,
                    instruction_details=sentinel.instruction_details,
                ),
                call(
                    mock_vault,
                    amount=Decimal("2"),
                    denomination=sentinel.denomination,
                    debit_account_id=sentinel.interest_write_off_internal_account,
                    credit_account_id=mock_vault.account_id,
                    instruction_details=sentinel.instruction_details,
                ),
            ]
        )
        self.mock_process_repayment.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            interest_instruction,
            sentinel.in_flight_balances,
            DEFAULT_DATETIME,
            account_id=mock_vault.account_id,
        )
        self.mock_adjust_aggregate_balances.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            sentinel.in_flight_balances,
            DEFAULT_DATETIME,
            credit_limit=sentinel.credit_limit,
        )


class RebalanceInterestTest(CreditCardTestBase):
    def setUp(self) -> None:
        self.mock_vault = self.create_mock()

        self.common_get_param_return_values: dict = {
            "credit_limit": sentinel.credit_limit,
        }
        patch_get_parameter = patch.object(credit_card.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values},
        )

        patch_get_supported_fee_types = patch.object(credit_card, "_get_supported_fee_types")
        self.mock_get_supported_fee_types = patch_get_supported_fee_types.start()
        self.mock_get_supported_fee_types.return_value = sentinel.supported_fee_types

        patch_determine_amount_breakdown = patch.object(credit_card, "_determine_amount_breakdown")
        self.mock_determine_amount_breakdown = patch_determine_amount_breakdown.start()

        patch_get_interest_internal_accounts = patch.object(
            credit_card, "_get_interest_internal_accounts"
        )
        self.mock_get_interest_internal_accounts = patch_get_interest_internal_accounts.start()
        self.mock_get_interest_internal_accounts.return_value = sentinel.income_account

        patch_create_custom_instructions = patch.object(credit_card, "_create_custom_instructions")
        self.mock_create_custom_instructions = patch_create_custom_instructions.start()
        self.mock_create_custom_instructions.return_value = [
            SentinelCustomInstruction("credit_extra_and_deposit_amount")
        ]

        patch_interest_address = patch.object(credit_card, "_interest_address")
        self.mock_interest_address = patch_interest_address.start()
        self.mock_interest_address.return_value = sentinel.interest_address

        patch_make_internal_address_transfer = patch.object(
            credit_card, "_make_internal_address_transfer"
        )
        self.mock_make_internal_address_transfer = patch_make_internal_address_transfer.start()
        self.mock_make_internal_address_transfer.return_value = [
            SentinelCustomInstruction("credit_and_extra_limit_amount")
        ]

        patch_make_deposit_postings = patch.object(credit_card, "_make_deposit_postings")
        self.mock_make_deposit_postings = patch_make_deposit_postings.start()
        self.mock_make_deposit_postings.return_value = [
            SentinelCustomInstruction("deposit_postings")
        ]

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_all_charged_interest_and_interest_instructions(self):
        # construct mocks
        # credit_line_amount + deposit_amount > 0
        # credit_line_amount > 0
        self.mock_determine_amount_breakdown.return_value = (
            Decimal("5"),  # credit_line_amount
            Decimal("6"),  # deposit_amount
        )

        # construct expected result
        expected_result = [
            SentinelCustomInstruction("credit_extra_and_deposit_amount"),
            SentinelCustomInstruction("credit_and_extra_limit_amount"),
            SentinelCustomInstruction("deposit_postings"),
        ]

        # run function
        instructions: list[CustomInstruction] = []
        credit_card._rebalance_interest(
            vault=self.mock_vault,
            amount=Decimal("11"),
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            charge_type=sentinel.charge_type,
            sub_type=sentinel.sub_type,
            instructions=instructions,
        )

        self.assertEqual(instructions, expected_result)
        self.mock_determine_amount_breakdown.assert_called_once_with(
            amount_to_charge=Decimal("11"),
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
        )
        self.mock_create_custom_instructions.assert_called_once_with(
            self.mock_vault,
            amount=Decimal("11"),  # credit_line_amount + deposit_amount,
            debit_account_id=self.mock_vault.account_id,
            debit_address=DEFAULT_ADDRESS,
            credit_account_id=sentinel.income_account,
            credit_address=DEFAULT_ADDRESS,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            instruction_details={},
        )
        self.mock_make_internal_address_transfer.assert_called_once_with(
            self.mock_vault,
            amount=Decimal("5"),  # credit_line_amount,
            denomination=sentinel.denomination,
            credit_internal=True,
            custom_address=sentinel.interest_address,
            instruction_details={},
            in_flight_balances=sentinel.in_flight_balances,
        )
        self.mock_make_deposit_postings.assert_called_once_with(
            vault=self.mock_vault,
            denomination=sentinel.denomination,
            amount=Decimal("6"),
            in_flight_balances=sentinel.in_flight_balances,
            instruction_details={},
        )

    def test_all_charged_interest_and_no_interest_instructions(self):
        # construct mocks
        # credit_line_amount + deposit_amount > 0
        # credit_line_amount  = 0
        self.mock_determine_amount_breakdown.return_value = (
            Decimal("0"),  # credit_line_amount
            Decimal("6"),  # deposit_amount
        )
        # construct expected result
        expected_result = [
            SentinelCustomInstruction("credit_extra_and_deposit_amount"),
            SentinelCustomInstruction("deposit_postings"),
        ]
        # run function
        instructions: list[CustomInstruction] = []
        credit_card._rebalance_interest(
            vault=self.mock_vault,
            amount=Decimal("6"),
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            charge_type=sentinel.charge_type,
            sub_type=sentinel.sub_type,
            instructions=instructions,
        )

        self.assertEqual(instructions, expected_result)
        self.mock_determine_amount_breakdown.assert_called_once_with(
            amount_to_charge=Decimal("6"),
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
        )
        self.mock_create_custom_instructions.assert_called_once_with(
            self.mock_vault,
            amount=Decimal("6"),  # credit_line_amount + extra_limit_amount + deposit_amount,
            debit_account_id=self.mock_vault.account_id,
            debit_address=DEFAULT_ADDRESS,
            credit_account_id=sentinel.income_account,
            credit_address=DEFAULT_ADDRESS,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            instruction_details={},
        )
        self.mock_make_internal_address_transfer.assert_not_called()
        self.mock_make_deposit_postings.assert_called_once_with(
            vault=self.mock_vault,
            denomination=sentinel.denomination,
            amount=Decimal("6"),
            in_flight_balances=sentinel.in_flight_balances,
            instruction_details={},
        )

    def test_zero_amount(self):
        # construct mocks
        # credit_line_amount + deposit_amount = 0
        # credit_line_amount  = 0
        self.mock_determine_amount_breakdown.return_value = (
            Decimal("0"),  # credit_line_amount
            Decimal("0"),  # deposit_amount
        )
        # construct expected result
        expected_result = [
            SentinelCustomInstruction("deposit_postings"),
        ]
        # run function
        instructions: list[CustomInstruction] = []
        credit_card._rebalance_interest(
            vault=self.mock_vault,
            amount=Decimal("0"),
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            charge_type=sentinel.charge_type,
            sub_type=sentinel.sub_type,
            instructions=instructions,
        )

        self.assertEqual(instructions, expected_result)
        self.mock_determine_amount_breakdown.assert_called_once_with(
            amount_to_charge=Decimal("0"),
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
        )
        self.mock_create_custom_instructions.assert_not_called()
        self.mock_make_internal_address_transfer.assert_not_called()
        self.mock_make_deposit_postings.assert_called_once_with(
            vault=self.mock_vault,
            denomination=sentinel.denomination,
            amount=Decimal("0"),
            in_flight_balances=sentinel.in_flight_balances,
            instruction_details={},
        )


class RepaySpendAndChargesTest(CreditCardTestBase):
    def setUp(self) -> None:
        self.mock_vault = sentinel.vault

        self.common_get_param_return_values: dict = {
            "transaction_annual_percentage_rate": {},
            "annual_percentage_rate": sentinel.annual_percentage_rate,
        }
        patch_get_parameter = patch.object(credit_card.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values},
        )

        patch_get_supported_txn_types = patch.object(credit_card, "_get_supported_txn_types")
        self.mock_get_supported_txn_types = patch_get_supported_txn_types.start()
        self.mock_get_supported_txn_types.return_value = sentinel.supported_txn_types

        patch_get_supported_fee_types = patch.object(credit_card, "_get_supported_fee_types")
        self.mock_get_supported_fee_types = patch_get_supported_fee_types.start()
        self.mock_get_supported_fee_types.return_value = sentinel.supported_fee_types

        patch_construct_stems = patch.object(credit_card, "_construct_stems")
        self.mock_construct_stems = patch_construct_stems.start()
        self.mock_construct_stems.return_value = sentinel.stems

        patch_order_stems_by_repayment_hierarchy = patch.object(
            credit_card, "_order_stems_by_repayment_hierarchy"
        )
        self.mock_order_stems_by_repayment_hierarchy = (
            patch_order_stems_by_repayment_hierarchy.start()
        )
        self.mock_order_stems_by_repayment_hierarchy.return_value = (
            sentinel.order_stems_by_repayment_hierarchy
        )

        patch_get_repayment_addresses = patch.object(credit_card, "_get_repayment_addresses")
        self.mock_get_repayment_addresses = patch_get_repayment_addresses.start()

        patch_get_denomination_from_posting_instruction = patch.object(
            credit_card, "get_denomination_from_posting_instruction"
        )
        self.mock_get_denomination_from_posting_instruction = (
            patch_get_denomination_from_posting_instruction.start()
        )
        self.mock_get_denomination_from_posting_instruction.return_value = sentinel.denomination

        patch_balance_at_coordinates = patch.object(credit_card.utils, "balance_at_coordinates")
        self.mock_balance_at_coordinates = patch_balance_at_coordinates.start()

        patch_make_internal_address_transfer = patch.object(
            credit_card, "_make_internal_address_transfer"
        )
        self.mock_make_internal_address_transfer = patch_make_internal_address_transfer.start()

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_positive_remaining_repayment_amount(self):
        # construct mocks
        self.mock_get_repayment_addresses.return_value = [
            (sentinel._, sentinel._, sentinel.address_1),
            (sentinel._, sentinel._, sentinel.address_2),
        ]
        self.mock_balance_at_coordinates.side_effect = [
            Decimal("20"),  # balance at address_1
            Decimal("30"),  # balance at address_2
        ]
        self.mock_make_internal_address_transfer.return_value = [
            SentinelCustomInstruction("address_1_repayment"),
            SentinelCustomInstruction("address_2_repayment"),
        ]

        remaining_repayment_amount = Decimal("90")
        # construct expected result
        # remaining_repayment_amount - balance at address_1 - balance at address_2
        # 90 - 20 - 30
        expected_result = Decimal("40")

        # run function
        result = credit_card._repay_spend_and_charges(
            vault=self.mock_vault,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
            repayment_posting_instructions=[],
            posting_instruction=sentinel.posting_instruction,
            remaining_repayment_amount=remaining_repayment_amount,
        )

        self.assertEqual(result, expected_result)
        self.mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.in_flight_balances,
                    address=sentinel.address_1,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.in_flight_balances,
                    address=sentinel.address_2,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        self.mock_make_internal_address_transfer.assert_has_calls(
            calls=[
                call(
                    self.mock_vault,
                    Decimal("20"),
                    sentinel.denomination,
                    credit_internal=False,
                    custom_address=sentinel.address_1,
                    in_flight_balances=sentinel.in_flight_balances,
                ),
                call(
                    self.mock_vault,
                    Decimal("30"),
                    sentinel.denomination,
                    credit_internal=False,
                    custom_address=sentinel.address_2,
                    in_flight_balances=sentinel.in_flight_balances,
                ),
            ]
        )

    def test_repayment_amount_less_than_balance_total(self):
        # construct mocks
        self.mock_get_repayment_addresses.return_value = [
            (sentinel._, sentinel._, sentinel.address_1),
            (sentinel._, sentinel._, sentinel.address_2),
        ]
        self.mock_balance_at_coordinates.side_effect = [
            Decimal("20"),  # balance at address_1
            Decimal("30"),  # balance at address_2
        ]
        self.mock_make_internal_address_transfer.return_value = [
            SentinelCustomInstruction("address_1_repayment"),
            SentinelCustomInstruction("address_2_repayment"),
        ]

        remaining_repayment_amount = Decimal("45")
        # construct expected result
        # remaining_repayment_amount - balance at address_1 - balance at address_2
        # 45 - 20 - min(30, 25) = 45 - 20 - 25
        expected_result = Decimal("0")

        # run function
        result = credit_card._repay_spend_and_charges(
            vault=self.mock_vault,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
            repayment_posting_instructions=[],
            posting_instruction=sentinel.posting_instruction,
            remaining_repayment_amount=remaining_repayment_amount,
        )

        self.assertEqual(result, expected_result)
        self.mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.in_flight_balances,
                    address=sentinel.address_1,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.in_flight_balances,
                    address=sentinel.address_2,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        self.mock_make_internal_address_transfer.assert_has_calls(
            calls=[
                call(
                    self.mock_vault,
                    Decimal("20"),
                    sentinel.denomination,
                    credit_internal=False,
                    custom_address=sentinel.address_1,
                    in_flight_balances=sentinel.in_flight_balances,
                ),
                call(
                    self.mock_vault,
                    Decimal("25"),
                    sentinel.denomination,
                    credit_internal=False,
                    custom_address=sentinel.address_2,
                    in_flight_balances=sentinel.in_flight_balances,
                ),
            ]
        )

    def test_repayment_amount_equal_balance_total(self):
        # construct mocks
        self.mock_get_repayment_addresses.return_value = [
            (sentinel._, sentinel._, sentinel.address_1),
            (sentinel._, sentinel._, sentinel.address_2),
        ]
        self.mock_balance_at_coordinates.side_effect = [
            Decimal("20"),  # balance at address_1
            Decimal("25"),  # balance at address_2
        ]
        self.mock_make_internal_address_transfer.return_value = [
            SentinelCustomInstruction("address_1_repayment"),
            SentinelCustomInstruction("address_2_repayment"),
        ]

        remaining_repayment_amount = Decimal("45")
        # construct expected result
        # remaining_repayment_amount - balance at address_1 - balance at address_2
        # 45 - 20 - min(25, 25) = 45 - 20 - 25
        expected_result = Decimal("0")

        # run function
        result = credit_card._repay_spend_and_charges(
            vault=self.mock_vault,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
            repayment_posting_instructions=[],
            posting_instruction=sentinel.posting_instruction,
            remaining_repayment_amount=remaining_repayment_amount,
        )

        self.assertEqual(result, expected_result)
        self.mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.in_flight_balances,
                    address=sentinel.address_1,
                    denomination=sentinel.denomination,
                ),
                call(
                    balances=sentinel.in_flight_balances,
                    address=sentinel.address_2,
                    denomination=sentinel.denomination,
                ),
            ]
        )
        self.mock_make_internal_address_transfer.assert_has_calls(
            calls=[
                call(
                    self.mock_vault,
                    Decimal("20"),
                    sentinel.denomination,
                    credit_internal=False,
                    custom_address=sentinel.address_1,
                    in_flight_balances=sentinel.in_flight_balances,
                ),
                call(
                    self.mock_vault,
                    Decimal("25"),
                    sentinel.denomination,
                    credit_internal=False,
                    custom_address=sentinel.address_2,
                    in_flight_balances=sentinel.in_flight_balances,
                ),
            ]
        )


@patch.object(credit_card, "_override_info_balance")
@patch.object(credit_card, "_age_overdue_address")
@patch.object(credit_card, "_get_overdue_balances")
class UpdateOverdueBucketsTest(CreditCardTestBase):
    def init_balances(self, balance_defs: list[dict[str, str]]) -> BalanceDefaultDict:
        """
        Returns a BalanceDefaultDict object.
        :param balance_defs: List(dict) the balances to construct. Each def is a dict with
        'address', 'denomination' 'phase' and 'asset' attributes for dimensions and 'net, 'debit',
        and 'credit' for the Balance. Dimensions default to their default value.
        :return: BalanceDefaultDict
        """
        balance_defs = balance_defs or []
        balance_dict = BalanceDefaultDict(
            None,
            {
                BalanceCoordinate(
                    account_address=balance_def.get("address", DEFAULT_ADDRESS).upper(),
                    asset=balance_def.get("asset", DEFAULT_ASSET),
                    denomination=balance_def.get("denomination", sentinel.denomination),
                    phase=Phase(balance_def.get("phase", Phase.COMMITTED)),
                ): Balance(
                    credit=Decimal(balance_def.get("credit", Decimal("0"))),
                    debit=Decimal(balance_def.get("debit", Decimal("0"))),
                    net=Decimal(balance_def.get("net", Decimal("0"))),
                )
                for balance_def in balance_defs
            },
        )

        return balance_dict

    def setUp(self):
        super().setUp()
        self.balances = self.init_balances(
            balance_defs=[
                {"address": "DEPOSIT", "net": "10000000000"},
                {"address": "PURCHASE_BILLED", "net": "1"},
                {"address": "CASH_ADVANCE_CHARGED", "net": "10"},
                {"address": "OVERDUE_1", "net": "100"},
                {"address": "OVERDUE_2", "net": "200"},
                {"address": "OVERDUE_3", "net": "300"},
            ]
        )

    def test_existing_overdue_balances_and_ci_returned(
        self,
        mock_get_overdue_balances: MagicMock,
        mock_age_overdue_address: MagicMock,
        mock_override_info_balance: MagicMock,
    ):
        # construct values
        posting_instructions_override_balance_overdue_buckets = [
            SentinelCustomInstruction("override_balance_bucket_OVERDUE_1"),
            SentinelCustomInstruction("override_balance_bucket_OVERDUE_2"),
            SentinelCustomInstruction("override_balance_bucket_OVERDUE_3"),
            SentinelCustomInstruction("override_balance_bucket_OVERDUE_4"),
        ]

        # construct mocks
        mock_get_overdue_balances.return_value = {
            "OVERDUE_1": Decimal("100"),
            "OVERDUE_2": Decimal("200"),
            "OVERDUE_3": Decimal("300"),
        }
        mock_age_overdue_address.side_effect = ["OVERDUE_2", "OVERDUE_3", "OVERDUE_4"]
        mock_override_info_balance.side_effect = [
            [SentinelCustomInstruction("override_balance_bucket_OVERDUE_1")],
            [SentinelCustomInstruction("override_balance_bucket_OVERDUE_2")],
            [SentinelCustomInstruction("override_balance_bucket_OVERDUE_3")],
            [SentinelCustomInstruction("override_balance_bucket_OVERDUE_4")],
        ]

        # expected result
        expected_result = posting_instructions_override_balance_overdue_buckets

        # run function
        result = credit_card._update_overdue_buckets(
            vault=sentinel.vault,
            overdue_total=sentinel.overdue_total,
            in_flight_balances=self.balances,
            denomination=sentinel.denomination,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_get_overdue_balances.assert_called_once_with(
            self.balances,
        )
        mock_age_overdue_address.assert_has_calls(
            calls=[
                call("OVERDUE_1"),
                call("OVERDUE_2"),
                call("OVERDUE_3"),
            ]
        )
        mock_override_info_balance.assert_has_calls(
            calls=[
                call(
                    sentinel.vault,
                    self.balances,
                    "OVERDUE_1",
                    sentinel.denomination,
                    sentinel.overdue_total,
                ),
                call(
                    sentinel.vault,
                    self.balances,
                    "OVERDUE_2",
                    sentinel.denomination,
                    Decimal("100"),
                ),
                call(
                    sentinel.vault,
                    self.balances,
                    "OVERDUE_3",
                    sentinel.denomination,
                    Decimal("200"),
                ),
                call(
                    sentinel.vault,
                    self.balances,
                    "OVERDUE_4",
                    sentinel.denomination,
                    Decimal("300"),
                ),
            ]
        )

    def test_no_existing_overdue_balances_and_ci_returned(
        self,
        mock_get_overdue_balances: MagicMock,
        mock_age_overdue_address: MagicMock,
        mock_override_info_balance: MagicMock,
    ):
        # construct values
        self.balances = self.init_balances(
            balance_defs=[
                {"address": "DEPOSIT", "net": "10000000000"},
            ]
        )
        posting_instructions_override_balance_overdue_buckets = [
            SentinelCustomInstruction("override_balance_bucket_OVERDUE_1"),
        ]

        # construct mocks
        mock_get_overdue_balances.return_value = {}

        mock_override_info_balance.side_effect = [
            [SentinelCustomInstruction("override_balance_bucket_OVERDUE_1")],
        ]

        # expected result
        expected_result = posting_instructions_override_balance_overdue_buckets

        # run function
        result = credit_card._update_overdue_buckets(
            vault=sentinel.vault,
            overdue_total=sentinel.overdue_total,
            in_flight_balances=self.balances,
            denomination=sentinel.denomination,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_get_overdue_balances.assert_called_once_with(
            self.balances,
        )
        mock_age_overdue_address.assert_not_called()
        mock_override_info_balance.assert_has_calls(
            calls=[
                call(
                    sentinel.vault,
                    self.balances,
                    "OVERDUE_1",
                    sentinel.denomination,
                    sentinel.overdue_total,
                ),
            ]
        )


class GetOverdueBalances(CreditCardTestBase):
    def test_overdue_balances_returned(self):
        # construct values
        balances = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ): Balance(net=Decimal("100")),
                BalanceCoordinate(
                    account_address="OVERDUE_1",
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ): Balance(net=Decimal("30")),
                BalanceCoordinate(
                    account_address="OVERDUE_2",
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ): Balance(net=Decimal("500")),
                BalanceCoordinate(
                    account_address="sentinel.account_address",
                    asset=DEFAULT_ASSET,
                    denomination=sentinel.denomination,
                    phase=Phase.COMMITTED,
                ): Balance(net=Decimal("8982")),
            },
        )

        # expected result
        expected_result = {"OVERDUE_1": Decimal("30"), "OVERDUE_2": Decimal("500")}

        # run function
        result = credit_card._get_overdue_balances(
            balances=balances,
        )

        # call assertions
        self.assertEqual(result, expected_result)


@patch.object(credit_card, "_create_custom_instructions")
class MoveFundsInternallyTest(CreditCardTestBase):
    def test_zero_or_negative_amount_and_no_ci_returned(
        self,
        mock_create_custom_instructions: MagicMock,
    ):
        result = credit_card._move_funds_internally(
            vault=sentinel.vault,
            amount=Decimal("0"),
            debit_address=sentinel.debit_address,
            credit_address=sentinel.credit_address,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
        )

        self.assertEqual(result, [])
        mock_create_custom_instructions.assert_not_called()

    def test_positive_amount_and_ci_returned(
        self,
        mock_create_custom_instructions: MagicMock,
    ):
        mock_create_custom_instructions.return_value = [
            SentinelCustomInstruction("move_funds_internally")
        ]
        mock_vault = self.create_mock()

        expected_result = [SentinelCustomInstruction("move_funds_internally")]

        result = credit_card._move_funds_internally(
            vault=mock_vault,
            amount=Decimal("100"),
            debit_address=sentinel.debit_address,
            credit_address=sentinel.credit_address,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
        )

        self.assertEqual(result, expected_result)
        mock_create_custom_instructions.assert_called_once_with(
            mock_vault,
            Decimal("100"),
            debit_account_id=mock_vault.account_id,
            credit_account_id=mock_vault.account_id,
            denomination=sentinel.denomination,
            debit_address=sentinel.debit_address,
            instruction_details={
                "description": "Move balance from sentinel.debit_address to "
                "sentinel.credit_address"
            },
            credit_address=sentinel.credit_address,
            in_flight_balances=sentinel.in_flight_balances,
        )


@patch.object(credit_card, "_get_first_pdd")
@patch.object(credit_card, "_get_first_scod")
class GetNextPddTest(CreditCardTestBase):
    def test_no_last_pdd_execution_and_first_pdd_returned(
        self,
        mock_get_first_scod: MagicMock,
        mock_get_first_pdd: MagicMock,
    ):
        mock_get_first_scod.return_value = (
            sentinel.first_SCOD_start_datetime,
            sentinel.first_SCOD_end_datetime,
        )
        mock_get_first_pdd.return_value = (
            sentinel.first_PDD_start_datetime,
            sentinel.first_PDD_end_datetime,
        )

        expected_result = sentinel.first_PDD_start_datetime, sentinel.first_PDD_end_datetime

        result = credit_card._get_next_pdd(
            payment_due_period=sentinel.payment_due_period,
            account_creation_datetime=sentinel.account_creation_date,
            last_pdd_execution_datetime=None,
        )

        self.assertEqual(result, expected_result)

    def test_calculated_next_pdd_returned(
        self,
        mock_get_first_scod: MagicMock,
        mock_get_first_pdd: MagicMock,
    ):
        # Account created in March, last PDD ran in May, next PDD in June.
        mock_get_first_scod.return_value = (
            datetime(2023, 3, 31, 0, 0, tzinfo=ZoneInfo("UTC")),
            sentinel.first_SCOD_end_datetime,
        )

        mock_get_first_pdd.return_value = (
            datetime(2023, 4, 21, 0, 0, tzinfo=ZoneInfo("UTC")),
            datetime(2023, 4, 21, 0, 0, tzinfo=ZoneInfo("UTC")) + relativedelta(days=1),
        )

        expected_next_pdd_start = datetime(
            2023, 4, 21, 0, 0, tzinfo=ZoneInfo("UTC")
        ) + relativedelta(months=2)
        expected_result = expected_next_pdd_start, expected_next_pdd_start + relativedelta(days=1)

        result = credit_card._get_next_pdd(
            payment_due_period=21,
            account_creation_datetime=datetime(2023, 3, 1, 10, 0, tzinfo=ZoneInfo("UTC")),
            last_pdd_execution_datetime=datetime(2023, 5, 21, 0, 0, tzinfo=ZoneInfo("UTC")),
        )

        self.assertEqual(result, expected_result)


class GetFirstScodTest(CreditCardTestBase):
    def test_first_scod_date_returned(self):
        # first SCOD start datetime should be 1 month after account creation, less 1 day, at 00:00H.
        expected_scod_start_datetime = datetime(2023, 3, 31, 0, 0, tzinfo=ZoneInfo("UTC"))

        expected_result = (
            expected_scod_start_datetime,
            expected_scod_start_datetime + relativedelta(days=1),
        )

        result = credit_card._get_first_scod(
            account_creation_datetime=datetime(2023, 3, 1, 10, 0, tzinfo=ZoneInfo("UTC"))
        )

        self.assertEqual(result, expected_result)


@patch.object(credit_card, "_make_internal_address_transfer")
class UpdateTotalRepaymentTrackerTest(CreditCardTestBase):
    def test_zero_or_negative_amount_repaid_and_no_ci_returned(
        self,
        mock_make_internal_address_transfer: MagicMock,
    ):
        result = credit_card._update_total_repayment_tracker(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            posting_instruction_denomination=sentinel.posting_instruction_denomination,
            amount_repaid=Decimal("-10"),
        )

        self.assertEqual(result, [])
        mock_make_internal_address_transfer.assert_not_called()

    def test_positive_amount_repaid_and_ci_returned(
        self,
        mock_make_internal_address_transfer: MagicMock,
    ):
        repayment_tracker_postings = [SentinelCustomInstruction("update_repayment_tracker")]

        mock_make_internal_address_transfer.return_value = repayment_tracker_postings

        expected_result = repayment_tracker_postings

        result = credit_card._update_total_repayment_tracker(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            posting_instruction_denomination=sentinel.posting_instruction_denomination,
            amount_repaid=Decimal("30"),
        )

        self.assertEqual(result, expected_result)
        mock_make_internal_address_transfer.assert_called_once_with(
            sentinel.vault,
            amount=Decimal("30"),
            denomination=sentinel.posting_instruction_denomination,
            credit_internal=True,
            custom_address=credit_card.TRACK_STATEMENT_REPAYMENTS,
            in_flight_balances=sentinel.in_flight_balances,
        )


@patch.object(credit_card, "_make_internal_address_transfer")
@patch.object(credit_card.utils, "get_parameter")
@patch.object(credit_card.utils, "has_parameter_value_changed")
class HandleCreditLimitChange(CreditCardTestBase):
    def test_credit_limit_not_changed_and_no_ci_returned(
        self,
        mock_has_parameter_value_changed: MagicMock,
        mock_get_parameter: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        # construct mocks
        mock_has_parameter_value_changed.return_value = False

        # run function
        result = credit_card._handle_credit_limit_change(
            vault=sentinel.vault,
            old_parameter_values=sentinel.old_parameter_values,
            updated_parameter_values=sentinel.updated_parameter_values,
        )

        # call assertions
        self.assertEqual(result, [])
        mock_get_parameter.assert_not_called()
        mock_make_internal_address_transfer.assert_not_called()

    def test_credit_limit_increased_and_ci_returned(
        self,
        mock_has_parameter_value_changed: MagicMock,
        mock_get_parameter: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        # construct values
        old_parameter_values: dict[str, credit_card.ParameterTypes] = {
            credit_card.PARAM_CREDIT_LIMIT: Decimal("1000")
        }
        updated_parameter_values: dict[str, credit_card.ParameterTypes] = {
            credit_card.PARAM_CREDIT_LIMIT: Decimal("8000")
        }

        # construct mocks
        mock_has_parameter_value_changed.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_DENOMINATION: "GBP"}
        )
        mock_make_internal_address_transfer.return_value = [
            SentinelCustomInstruction("credit_limit_change")
        ]

        # expected result
        expected_result = [SentinelCustomInstruction("credit_limit_change")]

        # run function
        result = credit_card._handle_credit_limit_change(
            vault=sentinel.vault,
            old_parameter_values=old_parameter_values,
            updated_parameter_values=updated_parameter_values,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_has_parameter_value_changed.assert_called_once_with(
            parameter_name=credit_card.PARAM_CREDIT_LIMIT,
            old_parameters=old_parameter_values,
            updated_parameters=updated_parameter_values,
        )
        mock_make_internal_address_transfer.assert_called_once_with(
            amount=Decimal("7000"),
            credit_internal=True,
            custom_address=credit_card.AVAILABLE_BALANCE,
            vault=sentinel.vault,
            denomination="GBP",
        )

    def test_credit_limit_decreased_and_ci_returned(
        self,
        mock_has_parameter_value_changed: MagicMock,
        mock_get_parameter: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        # construct mocks
        mock_has_parameter_value_changed.return_value = True
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_DENOMINATION: "GBP"}
        )
        mock_make_internal_address_transfer.return_value = [
            SentinelCustomInstruction("credit_limit_change")
        ]

        # expected result
        expected_result = [SentinelCustomInstruction("credit_limit_change")]

        # run function
        result = credit_card._handle_credit_limit_change(
            vault=sentinel.vault,
            old_parameter_values={credit_card.PARAM_CREDIT_LIMIT: Decimal("1000")},
            updated_parameter_values={credit_card.PARAM_CREDIT_LIMIT: Decimal("600")},
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_make_internal_address_transfer.assert_called_once_with(
            amount=Decimal("400"),
            credit_internal=False,
            custom_address=credit_card.AVAILABLE_BALANCE,
            vault=sentinel.vault,
            denomination="GBP",
        )


@patch.object(credit_card, "_move_funds_internally")
class MoveOutstandingStatementBalancesToUnpaid(CreditCardTestBase):
    supported_txn_types: dict[str, Optional[list[str]]] = {
        "PURCHASE": None,
        "CASH_ADVANCE": None,
        "TRANSFER": ["REF1", "REF2"],
    }  # txn_type:txn_ref

    supported_fee_types = ["ANNUAL_FEE", "DISPUTE_FEE"]

    posting_instruction_txn_type_principal = [
        SentinelCustomInstruction("txn_type_principal_to_unpaid")
    ]
    posting_instruction_txn_type_interest = [
        SentinelCustomInstruction("txn_type_interest_to_unpaid")
    ]
    posting_instruction_fee_type_fees = [SentinelCustomInstruction("fee_type_fees_to_unpaid")]
    posting_instruction_fee_type_interest = [
        SentinelCustomInstruction("fee_type_interest_to_unpaid")
    ]

    def init_balances(self, balance_defs: list[dict[str, str]]) -> BalanceDefaultDict:
        """
        Returns a BalanceDefaultDict object.
        :param balance_defs: List(dict) the balances to construct. Each def is a dict with
        'address', 'denomination' 'phase' and 'asset' attributes for dimensions and 'net, 'debit',
        and 'credit' for the Balance. Dimensions default to their default value.
        :return: BalanceDefaultDict
        """
        balance_defs = balance_defs or []
        balance_dict = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=balance_def.get("address", DEFAULT_ADDRESS).upper(),
                    asset=balance_def.get("asset", DEFAULT_ASSET),
                    denomination=balance_def.get("denomination", sentinel.denomination),
                    phase=Phase(balance_def.get("phase", Phase.COMMITTED)),
                ): Balance(
                    credit=Decimal(balance_def.get("credit", Decimal("0"))),
                    debit=Decimal(balance_def.get("debit", Decimal("0"))),
                    net=Decimal(balance_def.get("net", Decimal("0"))),
                )
                for balance_def in balance_defs
            },
        )

        return balance_dict

    def test_principal_only_balance_transfer_with_ref_and_ci_returned(
        self,
        mock_move_funds_internally: MagicMock,
    ):
        # construct values
        balances = self.init_balances(
            balance_defs=[
                {"address": "TRANSFER_REF1_BILLED", "net": "1"},
                {"address": "TRANSFER_REF2_BILLED", "net": "2"},
            ]
        )

        # construct mocks
        mock_move_funds_internally.side_effect = [
            self.posting_instruction_txn_type_principal,  # TRANSFER_REF1
            self.posting_instruction_txn_type_principal,  # TRANSFER_REF2
        ]
        mock_vault = self.create_mock()

        # expected result
        expected_result = [
            *self.posting_instruction_txn_type_principal,
            *self.posting_instruction_txn_type_principal,
        ]

        # run function
        result = credit_card._move_outstanding_statement_balances_to_unpaid(
            vault=mock_vault,
            in_flight_balances=balances,
            denomination=sentinel.denomination,
            supported_txn_types=self.supported_txn_types,
            supported_fee_types=self.supported_fee_types,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_move_funds_internally.assert_has_calls(
            calls=[
                call(
                    mock_vault,
                    amount=Decimal("1"),
                    debit_address="TRANSFER_REF1_UNPAID",
                    credit_address="TRANSFER_REF1_BILLED",
                    denomination=sentinel.denomination,
                    in_flight_balances=balances,
                ),
                call(
                    mock_vault,
                    amount=Decimal("2"),
                    debit_address="TRANSFER_REF2_UNPAID",
                    credit_address="TRANSFER_REF2_BILLED",
                    denomination=sentinel.denomination,
                    in_flight_balances=balances,
                ),
            ]
        )

    def test_principal_only_ci_returned(
        self,
        mock_move_funds_internally: MagicMock,
    ):
        # construct values
        balances = self.init_balances(
            balance_defs=[
                {"address": "PURCHASE_BILLED", "net": "1"},
            ]
        )

        # construct mocks
        mock_move_funds_internally.side_effect = [self.posting_instruction_txn_type_principal]
        mock_vault = self.create_mock()

        # expected result
        expected_result = self.posting_instruction_txn_type_principal

        # run function
        result = credit_card._move_outstanding_statement_balances_to_unpaid(
            vault=mock_vault,
            in_flight_balances=balances,
            denomination=sentinel.denomination,
            supported_txn_types=self.supported_txn_types,
            supported_fee_types=self.supported_fee_types,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_move_funds_internally.assert_called_once_with(
            mock_vault,
            amount=Decimal("1"),
            debit_address="PURCHASE_UNPAID",
            credit_address="PURCHASE_BILLED",
            denomination=sentinel.denomination,
            in_flight_balances=balances,
        )

    def test_principal_and_principal_interest_and_ci_returned(
        self,
        mock_move_funds_internally: MagicMock,
    ):
        # construct values
        balances = self.init_balances(
            balance_defs=[
                {"address": "PURCHASE_BILLED", "net": "1"},
                {"address": "PURCHASE_INTEREST_BILLED", "net": "10000"},
            ]
        )

        # construct mocks
        mock_move_funds_internally.side_effect = [
            self.posting_instruction_txn_type_principal,
            self.posting_instruction_txn_type_interest,
        ]
        mock_vault = self.create_mock()

        # expected result
        expected_result = (
            self.posting_instruction_txn_type_principal + self.posting_instruction_txn_type_interest
        )

        # run function
        result = credit_card._move_outstanding_statement_balances_to_unpaid(
            vault=mock_vault,
            in_flight_balances=balances,
            denomination=sentinel.denomination,
            supported_txn_types=self.supported_txn_types,
            supported_fee_types=self.supported_fee_types,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_move_funds_internally.assert_has_calls(
            calls=[
                call(
                    mock_vault,
                    amount=Decimal("1"),
                    debit_address="PURCHASE_UNPAID",
                    credit_address="PURCHASE_BILLED",
                    denomination=sentinel.denomination,
                    in_flight_balances=balances,
                ),
                call(
                    mock_vault,
                    amount=Decimal("10000"),
                    debit_address="PURCHASE_INTEREST_UNPAID",
                    credit_address="PURCHASE_INTEREST_BILLED",
                    denomination=sentinel.denomination,
                    in_flight_balances=balances,
                ),
            ]
        )

    def test_no_unpaid_billed_amount_and_no_ci_returned(
        self,
        mock_move_funds_internally: MagicMock,
    ):
        # construct values
        balances = self.init_balances(
            balance_defs=[
                {"address": "PURCHASE_BILLED", "net": "0"},
            ]
        )

        # run function
        result = credit_card._move_outstanding_statement_balances_to_unpaid(
            vault=self.create_mock(),
            in_flight_balances=balances,
            denomination=sentinel.denomination,
            supported_txn_types=self.supported_txn_types,
            supported_fee_types=self.supported_fee_types,
        )

        # call assertions
        self.assertEqual(result, [])
        mock_move_funds_internally.assert_not_called()

    def test_fees_and_fee_interest_and_ci_returned(
        self,
        mock_move_funds_internally: MagicMock,
    ):
        # construct values
        balances = self.init_balances(
            balance_defs=[
                {"address": "ANNUAL_FEE_INTEREST_BILLED", "net": "25"},
                {"address": "DISPUTE_FEES_BILLED", "net": "1000"},
            ]
        )

        # construct mocks
        mock_move_funds_internally.side_effect = [
            self.posting_instruction_fee_type_fees,
            self.posting_instruction_fee_type_interest,
        ]

        # expected result
        expected_result = (
            self.posting_instruction_fee_type_fees + self.posting_instruction_fee_type_interest
        )
        mock_vault = self.create_mock()

        # run function
        result = credit_card._move_outstanding_statement_balances_to_unpaid(
            vault=mock_vault,
            in_flight_balances=balances,
            denomination=sentinel.denomination,
            supported_txn_types=self.supported_txn_types,
            supported_fee_types=self.supported_fee_types,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_move_funds_internally.assert_has_calls(
            calls=[
                call(
                    mock_vault,
                    amount=Decimal("25"),
                    debit_address="ANNUAL_FEE_INTEREST_UNPAID",
                    credit_address="ANNUAL_FEE_INTEREST_BILLED",
                    denomination=sentinel.denomination,
                    in_flight_balances=balances,
                ),
                call(
                    mock_vault,
                    amount=Decimal("1000"),
                    debit_address="DISPUTE_FEES_UNPAID",
                    credit_address="DISPUTE_FEES_BILLED",
                    denomination=sentinel.denomination,
                    in_flight_balances=balances,
                ),
            ]
        )


@patch.object(credit_card, "_move_outstanding_statement_balances_to_unpaid")
@patch.object(credit_card, "_get_supported_fee_types")
@patch.object(credit_card, "_update_overdue_buckets")
@patch.object(credit_card.utils, "is_flag_in_list_applied")
class MoveOutstandingStatementTest(CreditCardTestBase):
    posting_instruction_update_overdue_buckets = [
        SentinelCustomInstruction("update overdue buckets")
    ]
    posting_instruction_move_oustanding_statement_balances_to_unpaid = [
        SentinelCustomInstruction("move oustanding statement balances to unpaid")
    ]

    def test_blocking_flags_overdue_true_and_unpaid_true_and_no_ci_returned(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_update_overdue_buckets: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_move_outstanding_statement_balances_to_unpaid: MagicMock,
    ):
        # construct mocks
        mock_is_flag_in_list_applied.side_effect = [True, True]

        # run function
        result = credit_card._move_outstanding_statement(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            denomination=sentinel.denomination,
            overdue_total=sentinel.overdue_total,
            supported_txn_types=sentinel.supported_txn_types,
            effective_datetime=sentinel.effective_datetime,
        )

        # call assertion
        self.assertEqual(result, [])
        mock_update_overdue_buckets.assert_not_called()
        mock_get_supported_fee_types.assert_not_called()
        mock_move_outstanding_statement_balances_to_unpaid.assert_not_called()

    def test_blocking_flags_overdue_false_and_unpaid_true_and_ci_returned(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_update_overdue_buckets: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_move_outstanding_statement_balances_to_unpaid: MagicMock,
    ):
        # construct mocks
        mock_is_flag_in_list_applied.side_effect = [False, True]
        mock_update_overdue_buckets.return_value = self.posting_instruction_update_overdue_buckets

        # expected result
        expected_result = self.posting_instruction_update_overdue_buckets

        # run function
        result = credit_card._move_outstanding_statement(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            denomination=sentinel.denomination,
            overdue_total=sentinel.overdue_total,
            supported_txn_types=sentinel.supported_txn_types,
            effective_datetime=sentinel.effective_datetime,
        )

        # call assertion
        self.assertEqual(result, expected_result)
        mock_update_overdue_buckets.assert_called_once_with(
            sentinel.vault,
            sentinel.overdue_total,
            sentinel.in_flight_balances,
            sentinel.denomination,
        )
        mock_get_supported_fee_types.assert_not_called()
        mock_move_outstanding_statement_balances_to_unpaid.assert_not_called()

    def test_blocking_flags_overdue_true_and_unpaid_false_and_ci_returned(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_update_overdue_buckets: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_move_outstanding_statement_balances_to_unpaid: MagicMock,
    ):
        # construct mocks
        mock_is_flag_in_list_applied.side_effect = [True, False]
        mock_get_supported_fee_types.return_value = sentinel.supported_fee_types
        mock_move_outstanding_statement_balances_to_unpaid.return_value = (
            self.posting_instruction_move_oustanding_statement_balances_to_unpaid
        )

        # expected result
        expected_result = self.posting_instruction_move_oustanding_statement_balances_to_unpaid

        # run function
        result = credit_card._move_outstanding_statement(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            denomination=sentinel.denomination,
            overdue_total=sentinel.overdue_total,
            supported_txn_types=sentinel.supported_txn_types,
            effective_datetime=sentinel.effective_datetime,
        )

        # call assertion
        self.assertEqual(result, expected_result)
        mock_update_overdue_buckets.assert_not_called()
        mock_get_supported_fee_types.assert_called_once_with(
            sentinel.vault,
            sentinel.supported_txn_types,
        )
        mock_move_outstanding_statement_balances_to_unpaid.assert_called_once_with(
            sentinel.vault,
            sentinel.in_flight_balances,
            sentinel.denomination,
            sentinel.supported_txn_types,
            sentinel.supported_fee_types,
        )

    def test_blocking_flags_overdue_false_and_unpaid_false_and_ci_returned(
        self,
        mock_is_flag_in_list_applied: MagicMock,
        mock_update_overdue_buckets: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_move_outstanding_statement_balances_to_unpaid: MagicMock,
    ):
        # construct mocks
        mock_is_flag_in_list_applied.side_effect = [False, False]
        mock_update_overdue_buckets.return_value = self.posting_instruction_update_overdue_buckets
        mock_get_supported_fee_types.return_value = sentinel.supported_fee_types
        mock_move_outstanding_statement_balances_to_unpaid.return_value = (
            self.posting_instruction_move_oustanding_statement_balances_to_unpaid
        )

        # expected result
        expected_result = [
            *self.posting_instruction_update_overdue_buckets,
            *self.posting_instruction_move_oustanding_statement_balances_to_unpaid,
        ]

        # run function
        result = credit_card._move_outstanding_statement(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            denomination=sentinel.denomination,
            overdue_total=sentinel.overdue_total,
            supported_txn_types=sentinel.supported_txn_types,
            effective_datetime=sentinel.effective_datetime,
        )

        # call assertion
        self.assertEqual(result, expected_result)
        mock_update_overdue_buckets.assert_called_once_with(
            sentinel.vault,
            sentinel.overdue_total,
            sentinel.in_flight_balances,
            sentinel.denomination,
        )
        mock_get_supported_fee_types.assert_called_once_with(
            sentinel.vault,
            sentinel.supported_txn_types,
        )
        mock_move_outstanding_statement_balances_to_unpaid.assert_called_once_with(
            sentinel.vault,
            sentinel.in_flight_balances,
            sentinel.denomination,
            sentinel.supported_txn_types,
            sentinel.supported_fee_types,
        )


class GLPostingMetadata(CreditCardTestBase):
    def test_repayment_false_and_instruction_details_returned(self):
        # expected result
        expected_result: dict[str, str] = {
            "accounting_event": sentinel.event,
            "account_id": sentinel.account_id,
        }

        # run function
        result = credit_card._gl_posting_metadata(
            event=sentinel.event,
            account_id=sentinel.account_id,
            repayment=False,
        )

        # call assertions
        self.assertEqual(result, expected_result)

    def test_repayment_true_and_instruction_details_returned(self):
        # expected result
        expected_result: dict[str, str] = {
            "accounting_event": "LOAN_REPAYMENT",
            "account_id": sentinel.account_id,
        }

        # run function
        result = credit_card._gl_posting_metadata(
            event=sentinel.event,
            account_id=sentinel.account_id,
            repayment=True,
        )

        # call assertions
        self.assertEqual(result, expected_result)

    def test_repayment_true_and_txn_type_and_instruction_details_returned(self):
        # expected result
        expected_result: dict[str, str] = {
            "accounting_event": "LOAN_REPAYMENT",
            "account_id": sentinel.account_id,
            "inst_type": "txn_type",
        }

        # run function
        result = credit_card._gl_posting_metadata(
            event=sentinel.event,
            account_id=sentinel.account_id,
            repayment=True,
            txn_type="TXN_TYPE",
        )

        # call assertions
        self.assertEqual(result, expected_result)

    def test_repayment_true_and_txn_type_and_value_date_and_instruction_details_returned(self):
        # expected result
        expected_result: dict[str, str] = {
            "accounting_event": "LOAN_REPAYMENT",
            "account_id": sentinel.account_id,
            "inst_type": "txn_type",
            "interest_value_datetime": str(DEFAULT_DATETIME),
        }

        # run function
        result = credit_card._gl_posting_metadata(
            event=sentinel.event,
            account_id=sentinel.account_id,
            repayment=True,
            txn_type="TXN_TYPE",
            interest_value_datetime=DEFAULT_DATETIME,
        )

        # call assertions
        self.assertEqual(result, expected_result)


@patch.object(credit_card, "_get_scod_for_pdd")
@patch.object(credit_card, "_get_next_pdd")
@patch.object(credit_card, "_get_previous_scod")
@patch.object(credit_card.utils, "get_parameter")
class CreateStatementNotification(CreditCardTestBase):
    def test_is_final_true_and_directive_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_get_previous_scod: MagicMock,
        mock_get_next_pdd: MagicMock,
        mock_get_scod_for_pdd: MagicMock,
    ):
        # construct values
        account_creation_datetime = datetime(2023, 3, 31, 9, 0, tzinfo=ZoneInfo("UTC"))
        last_scod_execution_datetime = datetime(2023, 4, 30, 0, 0, tzinfo=ZoneInfo("UTC"))
        statement_end = last_scod_execution_datetime + relativedelta(months=1, days=1)
        final_statement = Decimal("300")
        mad = Decimal("20")
        is_final = True

        # construct mock
        mock_vault = self.create_mock(
            creation_date=account_creation_datetime,
        )

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_PAYMENT_DUE_PERIOD: "21"}
        )

        mock_get_previous_scod.return_value = (
            last_scod_execution_datetime - relativedelta(days=1),
            last_scod_execution_datetime,
        )

        # expected result
        expected_result = AccountNotificationDirective(
            notification_type=credit_card.PUBLISH_STATEMENT_DATA_NOTIFICATION,
            notification_details={
                "account_id": str(mock_vault.account_id),
                "start_of_statement_period": str(last_scod_execution_datetime.date()),
                "end_of_statement_period": str(statement_end.date()),
                "current_statement_balance": "%0.2f" % final_statement,
                "minimum_amount_due": "%0.2f" % mad,
                "current_payment_due_date": "",
                "next_payment_due_date": "",
                "next_statement_cut_off": "",
                "is_final": str(is_final),
            },
        )

        # run function
        result = credit_card._create_statement_notification(
            vault=mock_vault,
            statement_end=statement_end,
            final_statement=final_statement,
            mad=mad,
            is_final=is_final,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_get_next_pdd.assert_not_called()
        mock_get_scod_for_pdd.assert_not_called()

    def test_is_final_false_and_directive_returned(
        self,
        mock_get_parameter: MagicMock,
        mock_get_previous_scod: MagicMock,
        mock_get_next_pdd: MagicMock,
        mock_get_scod_for_pdd: MagicMock,
    ):
        # construct values
        # account_creation_datetime: 2023-03-31 09:00H
        # payment due period       : 21 days
        # prev_scod_end            : 2023-05-30 00:00H
        # is_final                 : False
        # last_pdd_execution_time  : 2023-06-21 00:00H
        # last_scod_execution_time : 2023-05-30 00:00H
        # current_pdd_start        : 2023-07-20 00:00H
        # current_pdd_end          : 2023-07-21 00:00H
        # next_pdd_start           : 2023-08-20 00:00H
        # next_scod_start          : 2023-07-30 00:00H

        account_creation_date = datetime(2023, 3, 31, 9, 0, tzinfo=ZoneInfo("UTC"))
        last_scod_execution_dt = datetime(2023, 5, 30, 0, 0, tzinfo=ZoneInfo("UTC"))  # end_dt
        last_pdd_execution_dt = datetime(2023, 6, 20, 0, 0, tzinfo=ZoneInfo("UTC"))  # end_dt
        current_pdd_start = datetime(2023, 7, 20, 0, 0, tzinfo=ZoneInfo("UTC"))
        next_pdd_start = datetime(2023, 8, 20, 0, 0, tzinfo=ZoneInfo("UTC"))
        next_scod_start = next_pdd_start - relativedelta(days=21)  # 2023-07-30 0000H
        statement_end = last_scod_execution_dt + relativedelta(months=1)
        final_statement = Decimal("300")
        mad = Decimal("20")
        payment_due_period = 21
        is_final = False

        # construct mock
        mock_vault = self.create_mock(
            creation_date=account_creation_date,
            last_execution_datetimes={
                credit_card.EVENT_PDD: last_pdd_execution_dt,
            },
        )

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_PAYMENT_DUE_PERIOD: "21"}
        )

        mock_get_previous_scod.return_value = (
            last_scod_execution_dt - relativedelta(days=1),
            last_scod_execution_dt,
        )

        mock_get_next_pdd.side_effect = [
            (current_pdd_start, current_pdd_start + relativedelta(days=1)),
            (next_pdd_start, next_pdd_start + relativedelta(days=1)),
        ]

        mock_get_scod_for_pdd.return_value = (
            next_scod_start,
            next_scod_start + relativedelta(days=1),
        )

        # expected result
        expected_result = AccountNotificationDirective(
            notification_type=credit_card.PUBLISH_STATEMENT_DATA_NOTIFICATION,
            notification_details={
                "account_id": str(mock_vault.account_id),
                "start_of_statement_period": str(last_scod_execution_dt.date()),
                "end_of_statement_period": str((statement_end.date() - relativedelta(days=1))),
                "current_statement_balance": "%0.2f" % final_statement,
                "minimum_amount_due": "%0.2f" % mad,
                "current_payment_due_date": str(current_pdd_start.date()),
                "next_payment_due_date": str(next_pdd_start.date()),
                "next_statement_cut_off": str(next_scod_start.date()),
                "is_final": str(is_final),
            },
        )

        # run function
        result = credit_card._create_statement_notification(
            vault=mock_vault,
            statement_end=statement_end,
            final_statement=final_statement,
            mad=mad,
            is_final=is_final,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_get_scod_for_pdd.assert_called_once_with(
            payment_due_period,
            next_pdd_start,
        )
        current_pdd_end = current_pdd_start + relativedelta(days=1)
        mock_get_next_pdd.assert_has_calls(
            calls=[
                call(
                    payment_due_period,
                    account_creation_date,
                    last_pdd_execution_dt,
                ),
                call(payment_due_period, account_creation_date, current_pdd_end),
            ]
        )


class CombineTxnAndTypeRates(CreditCardTestBase):
    def test_merged_transaction_type_rate_and_transaction_level_reference_rate_returned(self):
        # construct values
        txn_type_rate: dict[str, str] = {
            "txn_type_one": "type_one_rate",
            "txn_type_two": "type_two_rate",
        }
        txn_level_rate: dict[str, dict[str, str]] = {
            "txn_type_level_one": {"REF1": "ref1_rate", "REF2": "ref2_rate"},
        }

        # expected result
        expected_result = {
            "txn_type_one": "type_one_rate",
            "txn_type_two": "type_two_rate",
            "txn_type_level_one_ref1": "ref1_rate",
            "txn_type_level_one_ref2": "ref2_rate",
        }

        # run function
        result = credit_card._combine_txn_and_type_rates(
            txn_level_rate=txn_level_rate,
            txn_type_rate=txn_type_rate,
        )

        # call assertions
        self.assertEqual(result, expected_result)


class GetRepaymentAddresses(CreditCardTestBase):
    def test_list_of_balance_addresses_for_repayment_returned(self):
        # construct values
        txn_types = [
            "cash_advance",
            "purchase",
        ]  # listed by decreasing PARAM_APR

        fee_types = ["withdrawal_fee"]

        # expected result
        expected_result: list[tuple[str, str, str]] = [
            ("INTEREST", "cash_advance", "CASH_ADVANCE_INTEREST_UNPAID"),
            ("INTEREST", "purchase", "PURCHASE_INTEREST_UNPAID"),
            ("INTEREST", "withdrawal_fee", "WITHDRAWAL_FEE_INTEREST_UNPAID"),
            ("INTEREST", "cash_advance", "CASH_ADVANCE_INTEREST_BILLED"),
            ("INTEREST", "purchase", "PURCHASE_INTEREST_BILLED"),
            ("INTEREST", "withdrawal_fee", "WITHDRAWAL_FEE_INTEREST_BILLED"),
            ("FEES", "withdrawal_fee", "withdrawal_feeS_UNPAID"),
            ("FEES", "withdrawal_fee", "withdrawal_feeS_BILLED"),
            ("PRINCIPAL", "cash_advance", "cash_advance_UNPAID"),
            ("PRINCIPAL", "cash_advance", "cash_advance_BILLED"),
            ("PRINCIPAL", "purchase", "purchase_UNPAID"),
            ("PRINCIPAL", "purchase", "purchase_BILLED"),
            ("PRINCIPAL", "cash_advance", "cash_advance_CHARGED"),
            ("PRINCIPAL", "purchase", "purchase_CHARGED"),
            ("INTEREST", "cash_advance", "CASH_ADVANCE_INTEREST_CHARGED"),
            ("INTEREST", "purchase", "PURCHASE_INTEREST_CHARGED"),
            ("INTEREST", "withdrawal_fee", "WITHDRAWAL_FEE_INTEREST_CHARGED"),
            ("FEES", "withdrawal_fee", "withdrawal_feeS_CHARGED"),
        ]
        # run function
        result = credit_card._get_repayment_addresses(
            repayment_hierarchy=credit_card.REPAYMENT_HIERARCHY,
            txn_types=txn_types,
            fee_types=fee_types,
        )

        # call assertions
        self.assertEqual(result, expected_result)


@patch.object(credit_card, "_make_internal_address_transfer")
@patch.object(credit_card, "_get_txn_type_and_ref_from_posting")
@patch.object(credit_card, "_get_unsettled_amount")
class RebalanceRelease(CreditCardTestBase):
    def test_zero_unsettled_amount_and_no_ci_returned(
        self,
        mock_get_unsettled_amount: MagicMock,
        mock_get_txn_type_and_ref_from_posting: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        # construct mocks
        mock_get_unsettled_amount.return_value = Decimal("0")

        # run function
        result = credit_card._rebalance_release(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            posting_instruction=sentinel.posting_instruction,
            client_transaction=sentinel.client_transaction,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=sentinel.effective_datetime,
        )

        # call assertions
        self.assertEqual(result, [])
        mock_get_txn_type_and_ref_from_posting.assert_not_called()
        mock_make_internal_address_transfer.assert_not_called()

    def test_non_zero_unsettled_amount_and_release_auth_ci_returned(
        self,
        mock_get_unsettled_amount: MagicMock,
        mock_get_txn_type_and_ref_from_posting: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        # construct values
        release_pi = [SentinelCustomInstruction("release_auth")]
        release_outbound_auth_pi = self.release_outbound_auth(unsettled_amount=Decimal("100"))

        # construct mocks
        mock_get_unsettled_amount.return_value = Decimal("100")
        mock_get_txn_type_and_ref_from_posting.return_value = ("TXN_TYPE", None)
        mock_make_internal_address_transfer.return_value = release_pi
        mock_vault = self.create_mock()

        # expected result
        expected_result = release_pi

        # run function
        result = credit_card._rebalance_release(
            vault=mock_vault,
            denomination=sentinel.denomination,
            posting_instruction=release_outbound_auth_pi,
            client_transaction=sentinel.client_transaction,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=sentinel.effective_datetime,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_get_txn_type_and_ref_from_posting.assert_called_once_with(
            mock_vault,
            release_outbound_auth_pi.instruction_details,
            sentinel.effective_datetime,
            upper_case_type=True,
        )
        mock_make_internal_address_transfer.assert_called_once_with(
            mock_vault,
            amount=Decimal("100"),
            denomination=sentinel.denomination,
            credit_internal=False,
            custom_address=f"TXN_TYPE_{credit_card.AUTH}",
            instruction_details=release_outbound_auth_pi.instruction_details,
            in_flight_balances=sentinel.in_flight_balances,
        )


@patch.object(credit_card, "_make_internal_address_transfer")
@patch.object(credit_card, "_get_txn_type_and_ref_from_posting")
class RebalanceOutboundAuth(CreditCardTestBase):
    def test_authorised_transaction_and_adjustment_ci_returned(
        self,
        mock_get_txn_type_and_ref_from_posting: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        # construct values
        adjustment_pi = [SentinelCustomInstruction("adjustment_pi")]
        outbound_auth_pi = self.outbound_auth(
            amount=Decimal("20"), denomination=sentinel.denomination
        )

        # construct mocks
        mock_get_txn_type_and_ref_from_posting.return_value = ("TXN_TYPE", "REF")
        mock_make_internal_address_transfer.return_value = adjustment_pi
        mock_vault = self.create_mock()

        # expected result
        expected_result = adjustment_pi

        # run function
        result = credit_card._rebalance_outbound_auth(
            vault=mock_vault,
            denomination=sentinel.denomination,
            posting_instruction=outbound_auth_pi,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=sentinel.effective_datetime,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_get_txn_type_and_ref_from_posting.assert_called_once_with(
            mock_vault,
            outbound_auth_pi.instruction_details,
            sentinel.effective_datetime,
            upper_case_type=True,
        )
        mock_make_internal_address_transfer.assert_called_once_with(
            amount=Decimal("20"),
            denomination=sentinel.denomination,
            custom_address=f"TXN_TYPE_REF_{credit_card.AUTH}",
            credit_internal=True,
            instruction_details=outbound_auth_pi.instruction_details,
            vault=mock_vault,
            in_flight_balances=sentinel.in_flight_balances,
        )


@patch.object(credit_card, "_make_internal_address_transfer")
@patch.object(credit_card, "_get_txn_type_and_ref_from_posting")
class RebalanceAuthAdjust(CreditCardTestBase):
    def test_auth_less_spend(
        self,
        mock_get_txn_type_and_ref_from_posting: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        # construct values
        auth_balance_adjustment_pi = [SentinelCustomInstruction("auth_balance_adjustment_pi")]
        auth_adjustment_pi = self.outbound_auth_adjust(
            amount=Decimal("-100"), _denomination=sentinel.denomination
        )

        # construct mocks
        mock_get_txn_type_and_ref_from_posting.return_value = ("TXN_TYPE", None)
        mock_make_internal_address_transfer.return_value = auth_balance_adjustment_pi
        mock_vault = self.create_mock()

        # expected result
        expected_result = auth_balance_adjustment_pi

        # run function
        result = credit_card._rebalance_auth_adjust(
            vault=mock_vault,
            denomination=sentinel.denomination,
            posting_instruction=auth_adjustment_pi,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=sentinel.effective_datetime,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_get_txn_type_and_ref_from_posting.assert_called_once_with(
            mock_vault,
            auth_adjustment_pi.instruction_details,
            sentinel.effective_datetime,
            upper_case_type=True,
        )
        mock_make_internal_address_transfer.assert_called_once_with(
            mock_vault,
            amount=Decimal("100"),
            denomination=sentinel.denomination,
            credit_internal=False,
            custom_address=f"TXN_TYPE_{credit_card.AUTH}",
            instruction_details=auth_adjustment_pi.instruction_details,
            in_flight_balances=sentinel.in_flight_balances,
        )

    def test_auth_more_spend(
        self,
        mock_get_txn_type_and_ref_from_posting: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        # construct values
        auth_balance_adjustment_pi = [SentinelCustomInstruction("auth_balance_adjustment_pi")]
        auth_adjustment_pi = self.outbound_auth_adjust(
            amount=Decimal("500"), _denomination=sentinel.denomination
        )

        # construct mocks
        mock_get_txn_type_and_ref_from_posting.return_value = ("TXN_TYPE", None)
        mock_make_internal_address_transfer.return_value = auth_balance_adjustment_pi
        mock_vault = self.create_mock()

        # expected result
        expected_result = auth_balance_adjustment_pi

        # run function
        result = credit_card._rebalance_auth_adjust(
            vault=mock_vault,
            denomination=sentinel.denomination,
            posting_instruction=auth_adjustment_pi,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=sentinel.effective_datetime,
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_get_txn_type_and_ref_from_posting.assert_called_once_with(
            mock_vault,
            auth_adjustment_pi.instruction_details,
            sentinel.effective_datetime,
            upper_case_type=True,
        )
        mock_make_internal_address_transfer.assert_called_once_with(
            mock_vault,
            amount=Decimal("500"),
            denomination=sentinel.denomination,
            credit_internal=True,
            custom_address=f"TXN_TYPE_{credit_card.AUTH}",
            instruction_details=auth_adjustment_pi.instruction_details,
            in_flight_balances=sentinel.in_flight_balances,
        )


class ReverseUnchargedInterest(CreditCardTestBase):
    @patch.object(credit_card, "_make_accrual_posting")
    @patch.object(credit_card.utils, "balance_at_coordinates")
    def test_reverses_all_uncharged_interest_ci_returned(
        self,
        mock_balance_at_coordinates: MagicMock,
        mock_make_accrual_posting: MagicMock,
    ):
        # construct values
        # TXN_TYPE_1 - Decimal 0 - so no instruction
        # TXN_TYPE_2 - accrued_outgoing > 0
        # TXN_TYPE_3 - has ref and accrued_outgoing>0
        # TXN_TYPE_4 - has ref and accrued_outgoing>0, txn_type ends with INTEREST_FREE_PERIOD
        supported_txn_types: dict[str, Optional[list[str]]] = {
            "TXN_TYPE_1": None,
            "TXN_TYPE_2": None,
            "TXN_TYPE_3": ["REF8"],
            "TXN_TYPE_4_" + credit_card.INTEREST_FREE_PERIOD: ["REF5"],
        }
        accrued_outgoing_TXN_TYPE_1 = Decimal("0")
        accrued_outgoing_TXN_TYPE_2 = Decimal("1")
        accrued_outgoing_TXN_TYPE_3_REF8 = Decimal("2")
        accrued_outgoing_TXN_TYPE_4_REF5 = Decimal("3")

        # construct mocks
        mock_balance_at_coordinates.side_effect = [
            accrued_outgoing_TXN_TYPE_1,
            accrued_outgoing_TXN_TYPE_2,
            accrued_outgoing_TXN_TYPE_3_REF8,
            accrued_outgoing_TXN_TYPE_4_REF5,
        ]
        mock_make_accrual_posting.side_effect = [
            [SentinelCustomInstruction("txn_type_2_accrual_posting")],
            [SentinelCustomInstruction("txn_type_3_ref8_accrual_posting")],
            [SentinelCustomInstruction("txn_type_4_ref5_accrual_posting")],
        ]

        # expected result
        expected_result: list[CustomInstruction] = [
            SentinelCustomInstruction("txn_type_2_accrual_posting"),
            SentinelCustomInstruction("txn_type_3_ref8_accrual_posting"),
            SentinelCustomInstruction("txn_type_4_ref5_accrual_posting"),
        ]

        # run function
        result = credit_card._reverse_uncharged_interest(
            vault=sentinel.vault,
            in_flight_balances=sentinel.in_flight_balances,
            denomination=sentinel.denomination,
            supported_txn_types=supported_txn_types,
            trigger="trigger",
        )

        # call assertions
        self.assertEqual(result, expected_result)
        mock_make_accrual_posting.assert_has_calls(
            calls=[
                call(
                    sentinel.vault,
                    accrual_amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    stem="TXN_TYPE_2",
                    instruction_details={
                        "description": "Uncharged interest reversed for TXN_TYPE_2 - trigger"
                    },
                    reverse=True,
                    accrual_type=None,
                ),
                call(
                    sentinel.vault,
                    accrual_amount=Decimal("2"),
                    denomination=sentinel.denomination,
                    stem="TXN_TYPE_3_REF8",
                    instruction_details={
                        "description": "Uncharged interest reversed for TXN_TYPE_3_REF8 - trigger"
                    },
                    reverse=True,
                    accrual_type=None,
                ),
                call(
                    sentinel.vault,
                    accrual_amount=Decimal("3"),
                    denomination=sentinel.denomination,
                    stem=f"TXN_TYPE_4_REF5_{credit_card.INTEREST_FREE_PERIOD}",
                    instruction_details={
                        "description": "Uncharged interest reversed for TXN_TYPE_4_REF5_"
                        f"{credit_card.INTEREST_FREE_PERIOD} - trigger"
                    },
                    reverse=True,
                    accrual_type=None,
                ),
            ]
        )


class DetermineTxnsCurrentlyInterestFree(CreditCardTestBase):
    def test_txn_types_with_and_without_ref_and_interest_free_setting_returned(self):
        # construct values
        txn_types_in_interest_free_period: dict[str, list[str]] = {
            "TXN_TYPE1": [],
            "TXN_TYPE2": ["REF2"],
        }

        # transaction types that do not use references
        base_interest_rates: dict[str, str] = {
            "TXN_TYPE1": "3.2",
            "TXN_TYPE3": "24.77",
        }

        # transaction types that use references
        txn_base_interest_rates: dict[str, dict[str, str]] = {
            "TXN_TYPE2": {"REF1": "4.5", "REF2": "32.76"}
        }

        # expected result
        # Expecting TXN_TYPE1 and TXN_TYPE2_REF2 to have base interest rates set to zero.
        expected_result = (
            {"TXN_TYPE1": "0.0", "TXN_TYPE3": "24.77"},
            {"TXN_TYPE2": {"REF1": "4.5", "REF2": "0.0"}},
        )

        # run function
        result = credit_card._determine_txns_currently_interest_free(
            txn_types_in_interest_free_period=txn_types_in_interest_free_period,
            base_interest_rates=base_interest_rates,
            txn_base_interest_rates=txn_base_interest_rates,
        )

        # call assertions
        self.assertEqual(result, expected_result)


class GetNonAdvicePostings(CreditCardTestBase):
    def test_non_advice_posting_instructions_returned(self):
        # construct values
        posting_instructions = [
            self.outbound_hard_settlement(amount=Decimal("1")),
            self.inbound_hard_settlement(amount=Decimal("1"), advice=True),
        ]
        # expected result
        expected_result = [self.outbound_hard_settlement(amount=Decimal("1"))]

        # run function
        result = credit_card._get_non_advice_postings(posting_instructions)

        # call assertions
        self.assertEqual(result, expected_result)

    def test_non_advice_posting_instructions_nothing_returned(self):
        # construct values
        posting_instructions = [
            self.inbound_hard_settlement(amount=Decimal("1"), advice=True),
        ]

        # run function
        result = credit_card._get_non_advice_postings(posting_instructions)

        # call assertions
        self.assertEqual(result, [])


@patch.object(credit_card, "_make_internal_address_transfer")
@patch.object(credit_card, "_get_overdue_address_age")
class RepayOverdueBuckets(CreditCardTestBase):
    @staticmethod
    def init_balances(balance_defs: list[dict[str, str]]) -> BalanceDefaultDict:
        """
        Returns a BalanceDefaultDict object.
        :param balance_defs: List(dict) the balances to construct. Each def is a dict with
        'address', 'denomination' 'phase' and 'asset' attributes for dimensions and 'net, 'debit',
        and 'credit' for the Balance. Dimensions default to their default value.
        :return: BalanceDefaultDict
        """
        balance_defs = balance_defs or []
        balance_dict = BalanceDefaultDict(
            mapping={
                BalanceCoordinate(
                    account_address=balance_def.get("address", DEFAULT_ADDRESS),
                    asset=balance_def.get("asset", DEFAULT_ASSET),
                    denomination=balance_def.get("denomination", sentinel.denomination),
                    phase=Phase(balance_def.get("phase", Phase.COMMITTED)),
                ): Balance(
                    credit=Decimal(balance_def.get("credit", Decimal("0"))),
                    debit=Decimal(balance_def.get("debit", Decimal("0"))),
                    net=Decimal(balance_def.get("net", Decimal("0"))),
                )
                for balance_def in balance_defs
            },
        )

        return balance_dict

    def setUp(self):
        super().setUp()
        self.in_flight_balances = self.init_balances(
            balance_defs=[
                {"address": "OVERDUE_1", "net": "10"},
                {"address": "OVERDUE_2", "net": "20"},
                {"address": "TESTING_9", "net": "99"},
                {"address": "OVERDUE_3", "net": "30"},
                {"address": "overdue_4", "net": "40"},  # case sensitive: this is ignored.
                {"address": "ABC_OVERDUE_5", "net": "50"},
                {"address": "over_due_6", "net": "60"},
                {"address": "OVERDUE_100", "net": "100"},
            ]
        )

    def test_repayment_amount_covers_two_oldest_overdue_and_pi_extended(
        self,
        mock_get_overdue_address_age: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        # Repayment amount fully covers oldest and second oldest overdue.
        # Third oldest overdue partially covered.
        # construct values

        repayment_pi_1 = [SentinelCustomInstruction("repayment_OVERDUE_100")]
        repayment_pi_2 = [SentinelCustomInstruction("repayment_OVERDUE_3")]
        repayment_pi_3 = [SentinelCustomInstruction("repayment_OVERDUE_2")]
        repayment_posting_instructions: list[CustomInstruction] = []

        # construct mocks
        mock_get_overdue_address_age.side_effect = [1, 2, 3, 100]
        mock_make_internal_address_transfer.side_effect = [
            repayment_pi_1,
            repayment_pi_2,
            repayment_pi_3,
        ]

        # expected result
        expected_repayment_posting_instructions = [
            *repayment_pi_1,
            *repayment_pi_2,
            *repayment_pi_3,
        ]

        # run function
        result = credit_card._repay_overdue_buckets(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            in_flight_balances=self.in_flight_balances,
            repayment_posting_instructions=repayment_posting_instructions,  # type: ignore
            repayment_amount=Decimal("140"),
        )

        # call assertions
        self.assertIsNone(result)
        self.assertListEqual(
            repayment_posting_instructions, expected_repayment_posting_instructions
        )
        mock_make_internal_address_transfer.assert_has_calls(
            calls=[
                call(
                    amount=Decimal("100"),
                    denomination=sentinel.denomination,
                    credit_internal=False,
                    custom_address="OVERDUE_100",
                    vault=sentinel.vault,
                    in_flight_balances=self.in_flight_balances,
                ),
                call(
                    amount=Decimal("30"),
                    denomination=sentinel.denomination,
                    credit_internal=False,
                    custom_address="OVERDUE_3",
                    vault=sentinel.vault,
                    in_flight_balances=self.in_flight_balances,
                ),
                call(
                    amount=Decimal("10"),
                    denomination=sentinel.denomination,
                    credit_internal=False,
                    custom_address="OVERDUE_2",
                    vault=sentinel.vault,
                    in_flight_balances=self.in_flight_balances,
                ),
            ]
        )

    def test_repayment_amount_zero_and_pi_not_extended(
        self,
        mock_get_overdue_address_age: MagicMock,
        mock_make_internal_address_transfer: MagicMock,
    ):
        # Repayment amount zero, repayment posting instructions not extended.
        # construct values
        repayment_posting_instructions: list[CustomInstruction] = []

        # construct mocks
        mock_get_overdue_address_age.side_effect = [1, 2, 3, 100]

        # run function
        result = credit_card._repay_overdue_buckets(
            vault=sentinel.vault,
            denomination=sentinel.denomination,
            in_flight_balances=self.in_flight_balances,
            repayment_posting_instructions=repayment_posting_instructions,  # type: ignore
            repayment_amount=Decimal("0"),
        )

        # call assertions
        self.assertIsNone(result)
        self.assertListEqual(repayment_posting_instructions, [])
        mock_make_internal_address_transfer.assert_not_called()


@patch.object(credit_card, "_clean_up_balance_inconsistencies")
@patch.object(credit_card, "_update_balances")
class HandleLiveBalanceChanges(CreditCardTestBase):
    def setUp(self):
        super().setUp()
        self.cut_off_datetime = datetime(2023, 1, 2, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
        self.live_balance_net = Decimal("1")
        self.in_flight_live_balances = BalanceDefaultDict(
            mapping={DEFAULT_COORDINATE: Balance(net=self.live_balance_net)}
        )
        self.posting_instructions: list[CustomInstruction] = [
            SentinelCustomInstruction("pdd_processing")
        ]
        self.clean_up_postings = [SentinelCustomInstruction("clean_up_balance_inconsistencies")]

    def test_live_balance_dt_equal_cutoff_dt_and_no_change_to_instructions_timeseries(
        self,
        mock_update_balances: MagicMock,
        mock_clean_up_balance_inconsistencies: MagicMock,
    ):
        # construct values
        live_ts_item_dt = self.cut_off_datetime
        instructions_timeseries: dict[datetime, list[CustomInstruction]] = {
            live_ts_item_dt: self.posting_instructions
        }

        # construct mocks
        bif_mapping = {
            credit_card.STATEMENT_CUTOFF_TO_LIVE_BALANCES_BIF_ID: defaultdict(
                None,
                {
                    DEFAULT_COORDINATE: self.construct_balance_timeseries(
                        dt=live_ts_item_dt,
                        net=self.live_balance_net,
                    ),
                },
            )
        }
        mock_vault = self.create_mock(
            balances_interval_fetchers_mapping=bif_mapping,
        )

        # expected result
        expected_instructions_timeseries = instructions_timeseries  # should be no change

        # run function
        result = credit_card._handle_live_balance_changes(
            vault=mock_vault,
            denomination=sentinel.denomination,
            cut_off_datetime=self.cut_off_datetime,
            instructions_timeseries=instructions_timeseries,
        )

        # call assertions
        self.assertIsNone(result)
        self.assertDictEqual(instructions_timeseries, expected_instructions_timeseries)
        mock_update_balances.assert_called_with(
            mock_vault.account_id,
            self.in_flight_live_balances,
            self.posting_instructions,
        )
        mock_clean_up_balance_inconsistencies.assert_not_called()

    def test_live_balances_gt_cut_off_yields_clean_up_postings(
        self,
        mock_update_balances: MagicMock,
        mock_clean_up_balance_inconsistencies: MagicMock,
    ):
        # live_balances_dt > cut_off_datetime
        # live_balance_dt (from live_ts_item_dt) not in instructions_timeseries

        # construct values
        live_ts_item_dt = self.cut_off_datetime + relativedelta(hours=3)
        instructions_timeseries: dict[datetime, list[CustomInstruction]] = {
            live_ts_item_dt - relativedelta(hours=2): self.posting_instructions
        }
        balance_pairs = (credit_card.CHARGED, credit_card.BILLED)

        # construct mocks
        bif_mapping = {
            credit_card.STATEMENT_CUTOFF_TO_LIVE_BALANCES_BIF_ID: defaultdict(
                None,
                {
                    DEFAULT_COORDINATE: self.construct_balance_timeseries(
                        dt=live_ts_item_dt,
                        net=self.live_balance_net,
                    ),
                },
            )
        }

        mock_vault = self.create_mock(
            balances_interval_fetchers_mapping=bif_mapping,
        )

        mock_clean_up_balance_inconsistencies.return_value = self.clean_up_postings

        # expected_result
        expected_instructions_timeseries_at_live_balance_dt = self.clean_up_postings

        # run function
        self.assertIsNone(
            credit_card._handle_live_balance_changes(
                vault=mock_vault,
                denomination=sentinel.denomination,
                cut_off_datetime=self.cut_off_datetime,
                instructions_timeseries=instructions_timeseries,
            )
        )

        # call assertions
        self.assertEqual(
            instructions_timeseries[live_ts_item_dt],
            expected_instructions_timeseries_at_live_balance_dt,
        )

        mock_update_balances.assert_called_once_with(
            mock_vault.account_id,
            self.in_flight_live_balances,
            self.posting_instructions,
        )
        mock_clean_up_balance_inconsistencies.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            self.in_flight_live_balances,
            balance_pairs,
        )

    def test_live_balances_gt_cut_off_with_existing_postings_in_timeseries(
        self,
        mock_update_balances: MagicMock,
        mock_clean_up_balance_inconsistencies: MagicMock,
    ):
        # live_balances_dt > cut_off_datetime
        # live_balance_dt (from live_ts_item_dt) in instructions_timeseries

        # construct values
        live_ts_item_dt = self.cut_off_datetime + relativedelta(hours=3)
        instructions_timeseries: dict[datetime, list[CustomInstruction]] = {
            live_ts_item_dt: self.posting_instructions
        }
        balance_pairs = (credit_card.CHARGED, credit_card.BILLED)

        # construct mocks
        bif_mapping = {
            credit_card.STATEMENT_CUTOFF_TO_LIVE_BALANCES_BIF_ID: defaultdict(
                None,
                {
                    DEFAULT_COORDINATE: self.construct_balance_timeseries(
                        dt=live_ts_item_dt,
                        net=self.live_balance_net,
                    ),
                },
            )
        }

        mock_vault = self.create_mock(
            balances_interval_fetchers_mapping=bif_mapping,
        )

        mock_clean_up_balance_inconsistencies.return_value = self.clean_up_postings

        # expected_result
        expected_instructions_timeseries_at_live_balance_dt = [
            *self.posting_instructions,
            *self.clean_up_postings,
        ]

        # run function
        self.assertIsNone(
            credit_card._handle_live_balance_changes(
                vault=mock_vault,
                denomination=sentinel.denomination,
                cut_off_datetime=self.cut_off_datetime,
                instructions_timeseries=instructions_timeseries,
            )
        )

        # call assertions
        self.assertEqual(
            instructions_timeseries[live_ts_item_dt],
            expected_instructions_timeseries_at_live_balance_dt,
        )

        mock_update_balances.assert_called_once_with(
            mock_vault.account_id,
            self.in_flight_live_balances,
            self.posting_instructions,
        )
        mock_clean_up_balance_inconsistencies.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            self.in_flight_live_balances,
            balance_pairs,
        )


# this mocks the deposit balance
@patch.object(credit_card.utils, "balance_at_coordinates", MagicMock(return_value=Decimal("10")))
@patch.object(
    credit_card.utils,
    "get_parameter",
    MagicMock(
        side_effect=mock_utils_get_parameter(
            parameters={
                credit_card.PARAM_EXTERNAL_FEE_TYPES: ["dispute_fee", "withdrawal_fee"],
                credit_card.PARAM_TXN_TYPES: {"TXN_TYPE2": {}},
                credit_card.PARAM_TXN_REFS: {"TXN_TYPE2": ["REF8"]},
            }
        )
    ),
)
class RebalanceOutboundSettlementTest(CreditCardTestBase):
    def setUp(self) -> None:
        self.update_auth_bucket_pi = SentinelCustomInstruction(
            "update_auth_bucket_for_outbound_settlement"
        )
        self.mock_update_auth_bucket_for_outbound_settlement = patch.object(
            credit_card, "_update_auth_bucket_for_outbound_settlement"
        ).start()
        self.mock_update_auth_bucket_for_outbound_settlement.return_value = [
            self.update_auth_bucket_pi
        ]

        self.external_fee_pi = SentinelCustomInstruction("charge_external_fee")
        self.mock_charge_fee = patch.object(credit_card, "_charge_fee").start()
        self.mock_charge_fee.return_value = sentinel.fee_amount, [self.external_fee_pi]

        self.update_charged_bucket_pi = SentinelCustomInstruction("update_charged_bucket")
        self.mock_make_internal_address_transfer = patch.object(
            credit_card, "_make_internal_address_transfer"
        ).start()
        self.mock_make_internal_address_transfer.return_value = [self.update_charged_bucket_pi]

        self.make_deposit_postings_pi = SentinelCustomInstruction("make_deposit_postings")
        self.mock_make_deposit_postings = patch.object(
            credit_card, "_make_deposit_postings"
        ).start()
        self.mock_make_deposit_postings.return_value = [self.make_deposit_postings_pi]

        self.mock_get_txn_type_and_ref_from_posting = patch.object(
            credit_card,
            "_get_txn_type_and_ref_from_posting",
            MagicMock(return_value=("TXN_TYPE2", "REF8")),
        ).start()

        self.addCleanup(patch.stopall)

        return super().setUp()

    def test_charge_external_fee(self):
        # construct values
        client_transaction = ClientTransaction(
            account_id=ACCOUNT_ID,
            client_transaction_id=sentinel.client_transaction_id,
            posting_instructions=[
                self.outbound_auth(
                    amount=Decimal("88"),
                    denomination=sentinel.denomination,
                    instruction_details={credit_card.FEE_TYPE: "withdrawal_fee"},
                ),
                self.settle_outbound_auth(
                    unsettled_amount=Decimal("88"),
                    _denomination=sentinel.denomination,
                    instruction_details={credit_card.FEE_TYPE: "withdrawal_fee"},
                    value_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
                ),
            ],
            tside=credit_card.tside,
        )

        # construct mocks
        mock_vault = self.create_mock()

        # expected result
        expected_result = [self.external_fee_pi]

        # run function
        result = credit_card._rebalance_outbound_settlement(
            vault=mock_vault,
            client_transaction=client_transaction,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
        )

        # call assertions
        self.assertListEqual(result, expected_result)
        self.mock_charge_fee.assert_called_once_with(
            vault=mock_vault,
            denomination=sentinel.denomination,
            in_flight_balances=sentinel.in_flight_balances,
            fee_type="withdrawal_fee",
            fee_amount=Decimal("88"),
            is_external_fee=True,
        )
        self.mock_get_txn_type_and_ref_from_posting.assert_not_called()
        self.mock_update_auth_bucket_for_outbound_settlement.assert_not_called()
        self.mock_make_internal_address_transfer.assert_not_called()
        self.mock_make_deposit_postings.assert_not_called()

    def test_non_settlement_posting_into_credit_line(self):
        # construct values
        client_transaction = ClientTransaction(
            account_id=ACCOUNT_ID,
            client_transaction_id=sentinel.client_transaction_id,
            posting_instructions=[
                self.outbound_hard_settlement(
                    # deposit balance is 10, so this instruction exceeds that amount
                    amount=Decimal("100"),
                    denomination=sentinel.denomination,
                    instruction_details={"instruction": "details"},
                ),
            ],
            tside=credit_card.tside,
        )

        # construct mocks
        mock_vault = self.create_mock()
        # expected result
        expected_result = [self.update_charged_bucket_pi, self.make_deposit_postings_pi]

        # run function
        result = credit_card._rebalance_outbound_settlement(
            vault=mock_vault,
            client_transaction=client_transaction,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=sentinel.effective_datetime,
        )

        # call assertions
        self.assertListEqual(result, expected_result)
        self.mock_charge_fee.assert_not_called()
        self.mock_get_txn_type_and_ref_from_posting.assert_called_once_with(
            vault=mock_vault,
            instruction_details={"instruction": "details"},
            effective_datetime=sentinel.effective_datetime,
            supported_txn_types={"TXN_TYPE2": ["REF8"]},
            upper_case_type=True,
        )
        self.mock_update_auth_bucket_for_outbound_settlement.assert_not_called()
        self.mock_make_internal_address_transfer.assert_called_once_with(
            vault=mock_vault,
            amount=Decimal("90"),
            denomination=sentinel.denomination,
            custom_address="TXN_TYPE2_REF8_CHARGED",
            credit_internal=True,
            instruction_details={"instruction": "details"},
            in_flight_balances=sentinel.in_flight_balances,
        )
        self.mock_make_deposit_postings.assert_called_once_with(
            vault=mock_vault,
            denomination=sentinel.denomination,
            amount=Decimal("10"),  # deposit_spend
            in_flight_balances=sentinel.in_flight_balances,
            instruction_details={},
        )

    def test_non_settlement_posting_not_into_credit_line(self):
        # construct values
        client_transaction = ClientTransaction(
            account_id=ACCOUNT_ID,
            client_transaction_id=sentinel.client_transaction_id,
            posting_instructions=[
                self.outbound_hard_settlement(
                    # deposit balance is 10, so this instruction does not exceed that amount
                    amount=Decimal("5"),
                    denomination=sentinel.denomination,
                    instruction_details={"instruction": "details"},
                ),
            ],
            tside=credit_card.tside,
        )

        # construct mocks
        mock_vault = self.create_mock()
        # expected result
        expected_result = [self.make_deposit_postings_pi]

        # run function
        result = credit_card._rebalance_outbound_settlement(
            vault=mock_vault,
            client_transaction=client_transaction,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=sentinel.effective_datetime,
        )

        # call assertions
        self.assertListEqual(result, expected_result)
        self.mock_charge_fee.assert_not_called()
        self.mock_get_txn_type_and_ref_from_posting.assert_called_once_with(
            vault=mock_vault,
            instruction_details={"instruction": "details"},
            effective_datetime=sentinel.effective_datetime,
            supported_txn_types={"TXN_TYPE2": ["REF8"]},
            upper_case_type=True,
        )
        self.mock_update_auth_bucket_for_outbound_settlement.assert_not_called()
        self.mock_make_internal_address_transfer.assert_not_called()
        self.mock_make_deposit_postings.assert_called_once_with(
            vault=mock_vault,
            denomination=sentinel.denomination,
            amount=Decimal("5"),
            in_flight_balances=sentinel.in_flight_balances,
            instruction_details={},
        )

    def test_settlement_posting_above_deposit(self):
        # construct values
        client_transaction = ClientTransaction(
            account_id=ACCOUNT_ID,
            client_transaction_id=sentinel.client_transaction_id,
            posting_instructions=[
                self.outbound_auth(
                    amount=Decimal("100"),
                    denomination=sentinel.denomination,
                    instruction_details={"instruction": "details"},
                ),
                self.settle_outbound_auth(
                    unsettled_amount=Decimal("100"),
                    # deposit balance is 10, so this instruction exceeds that amount
                    amount=Decimal("100"),
                    _denomination=sentinel.denomination,
                    instruction_details={"instruction": "details"},
                    value_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
                ),
            ],
            tside=credit_card.tside,
        )

        # construct mocks
        mock_vault = self.create_mock()
        # expected result
        expected_result = [
            self.update_auth_bucket_pi,
            self.update_charged_bucket_pi,
            self.make_deposit_postings_pi,
        ]

        # run function
        result = credit_card._rebalance_outbound_settlement(
            vault=mock_vault,
            client_transaction=client_transaction,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
        )

        # call assertions
        self.assertListEqual(result, expected_result)
        self.mock_charge_fee.assert_not_called()
        self.mock_get_txn_type_and_ref_from_posting.assert_called_once_with(
            vault=mock_vault,
            instruction_details={"instruction": "details"},
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            supported_txn_types={"TXN_TYPE2": ["REF8"]},
            upper_case_type=True,
        )
        self.mock_update_auth_bucket_for_outbound_settlement.assert_called_once_with(
            vault=mock_vault,
            client_transaction=client_transaction,
            in_flight_balances=sentinel.in_flight_balances,
            txn_type="TXN_TYPE2",
            txn_ref="REF8",
        )
        self.mock_make_internal_address_transfer.assert_called_once_with(
            vault=mock_vault,
            amount=Decimal("90"),
            denomination=sentinel.denomination,
            custom_address="TXN_TYPE2_REF8_CHARGED",
            credit_internal=True,
            instruction_details={"instruction": "details"},
            in_flight_balances=sentinel.in_flight_balances,
        )
        self.mock_make_deposit_postings.assert_called_once_with(
            vault=mock_vault,
            denomination=sentinel.denomination,
            amount=Decimal("10"),
            in_flight_balances=sentinel.in_flight_balances,
            instruction_details={},
        )

    def test_settlement_posting_not_into_credit_line(self):
        # construct values
        client_transaction = ClientTransaction(
            account_id=ACCOUNT_ID,
            client_transaction_id=sentinel.client_transaction_id,
            posting_instructions=[
                self.outbound_auth(
                    amount=Decimal("10"),
                    denomination=sentinel.denomination,
                    instruction_details={"instruction": "details"},
                ),
                self.settle_outbound_auth(
                    unsettled_amount=Decimal("10"),
                    # deposit balance is 10, so this instruction does not exceed that amount
                    amount=Decimal("5"),
                    _denomination=sentinel.denomination,
                    instruction_details={"instruction": "details"},
                    value_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
                ),
            ],
            tside=credit_card.tside,
        )

        # construct mocks
        mock_vault = self.create_mock()
        # expected result
        expected_result = [
            self.update_auth_bucket_pi,
            self.make_deposit_postings_pi,
        ]

        # run function
        result = credit_card._rebalance_outbound_settlement(
            vault=mock_vault,
            client_transaction=client_transaction,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
        )

        # call assertions
        self.assertListEqual(result, expected_result)
        self.mock_charge_fee.assert_not_called()
        self.mock_get_txn_type_and_ref_from_posting.assert_called_once_with(
            vault=mock_vault,
            instruction_details={"instruction": "details"},
            effective_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
            supported_txn_types={"TXN_TYPE2": ["REF8"]},
            upper_case_type=True,
        )
        self.mock_update_auth_bucket_for_outbound_settlement.assert_called_once_with(
            vault=mock_vault,
            client_transaction=client_transaction,
            in_flight_balances=sentinel.in_flight_balances,
            txn_type="TXN_TYPE2",
            txn_ref="REF8",
        )
        self.mock_make_internal_address_transfer.assert_not_called()
        self.mock_make_deposit_postings.assert_called_once_with(
            vault=mock_vault,
            denomination=sentinel.denomination,
            amount=Decimal("5"),
            in_flight_balances=sentinel.in_flight_balances,
            instruction_details={},
        )


class ConstructStemsTest(CreditCardTestBase):
    def test_construct_stems_with_and_without_refs(self):
        # construct values
        txn_types: dict[str, Optional[list[str]]] = {
            "txn_type_no_refs": None,
            "txn_type_one_refs": ["ref1"],
            "txn_type_two_refs": ["ref1", "ref2"],
        }

        expected_result = [
            "txn_type_no_refs",
            "txn_type_one_refs_ref1",
            "txn_type_two_refs_ref1",
            "txn_type_two_refs_ref2",
        ]

        # run function
        result = credit_card._construct_stems(txn_types=txn_types)
        self.assertEqual(expected_result, result)


@patch.object(credit_card, "_move_funds_internally")
@patch.object(credit_card.utils, "balance_at_coordinates")
@patch.object(credit_card, "_principal_address")
class CleanUpBalanceInconsistenciesTest(CreditCardTestBase):
    def test_clean_up_balance_inconsistencies(
        self,
        mock_principal_address: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_move_funds_internally: MagicMock,
    ):
        # construct values
        address_suffix_pair = (credit_card.CHARGED, credit_card.BILLED)
        updated_live_balances = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(
                    account_address="TEST_CHARGED",
                    denomination=self.default_denomination,
                ): sentinel.balance
            }
        )
        clean_up_instructions = [SentinelCustomInstruction("clean_up_instructions")]

        # expected result
        expected_result = clean_up_instructions

        # construct mocks
        mock_principal_address.side_effect = [sentinel.debit_address, sentinel.credit_address]
        mock_balance_at_coordinates.side_effect = [Decimal("-1"), Decimal("1")]
        mock_move_funds_internally.return_value = clean_up_instructions

        # run function
        result = credit_card._clean_up_balance_inconsistencies(
            vault=sentinel.vault,
            denomination=self.default_denomination,
            updated_live_balances=updated_live_balances,
            address_suffix_pair=address_suffix_pair,
        )
        self.assertEqual(expected_result, result)

        # call assertions
        mock_principal_address.assert_has_calls(
            calls=[
                call("TEST", credit_card.CHARGED),
                call("TEST", credit_card.BILLED),
            ]
        )
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=updated_live_balances,
                    address=sentinel.debit_address,
                    denomination=self.default_denomination,
                ),
                call(
                    balances=updated_live_balances,
                    address=sentinel.credit_address,
                    denomination=self.default_denomination,
                ),
            ]
        )
        mock_move_funds_internally.assert_called_once_with(
            sentinel.vault,
            Decimal("1"),
            sentinel.debit_address,
            sentinel.credit_address,
            self.default_denomination,
            in_flight_balances=None,
        )


class CheckAccountHasSufficientFundsTest(CreditCardTestBase):
    @patch.object(credit_card, "_get_available_balance")
    @patch.object(credit_card, "_update_balances")
    def test_available_balance_delta_greater_than_zero(
        self,
        mock_update_balances: MagicMock,
        mock_get_available_balance: MagicMock,
    ):
        # construct values
        def _update_balances_side_effect(
            account_id,
            balances,
            posting_instructions,
        ):
            balances.update(BalanceDefaultDict())

        available_balance_delta = Decimal("1")

        # construct mocks
        mock_vault = self.create_mock()
        mock_update_balances.side_effect = _update_balances_side_effect
        mock_get_available_balance.return_value = available_balance_delta

        # run function
        result = credit_card._check_account_has_sufficient_funds(
            vault=mock_vault,
            balances=sentinel.balances,
            denomination=self.default_denomination,
            posting_instructions=[sentinel.posting_instruction],
        )
        self.assertIsNone(result)

        # assert calls
        mock_update_balances.assert_called_once_with(
            mock_vault.account_id,
            BalanceDefaultDict(),
            [sentinel.posting_instruction],
        )
        mock_get_available_balance.assert_called_once_with(
            Decimal("0"), BalanceDefaultDict(), {}, self.default_denomination
        )

    @patch.object(credit_card, "_get_overlimit_amount")
    @patch.object(credit_card.utils, "get_parameter")
    @patch.object(credit_card, "_get_supported_txn_types")
    @patch.object(credit_card, "_get_available_balance")
    @patch.object(credit_card, "_update_balances")
    def test_overlimit_amount_greater_than_zero(
        self,
        mock_update_balances: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_get_supported_txn_types: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_overlimit_amount: MagicMock,
    ):
        # construct values
        def _update_balances_side_effect(
            account_id,
            balances,
            posting_instructions,
        ):
            balances.update(BalanceDefaultDict())

        available_balance_delta = Decimal("-1")

        # expected rejection
        expected_rejection = Rejection(
            message=f"Insufficient funds for {self.default_denomination} "
            f"{-available_balance_delta} transaction. Overlimit already in use",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )

        # construct mocks
        mock_vault = self.create_mock()
        mock_update_balances.side_effect = _update_balances_side_effect
        mock_get_available_balance.side_effect = [available_balance_delta, Decimal("1")]
        mock_get_supported_txn_types.return_value = sentinel.supported_txn_types
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={credit_card.PARAM_CREDIT_LIMIT: sentinel.credit_limit}
        )
        mock_get_overlimit_amount.return_value = Decimal("1")

        # run function
        result = credit_card._check_account_has_sufficient_funds(
            vault=mock_vault,
            balances=sentinel.balances,
            denomination=self.default_denomination,
            posting_instructions=[sentinel.posting_instruction],
        )
        self.assertEqual(expected_rejection, result)

        # assert calls
        mock_update_balances.assert_called_once_with(
            mock_vault.account_id,
            BalanceDefaultDict(),
            [sentinel.posting_instruction],
        )
        mock_get_available_balance.assert_has_calls(
            calls=[
                call(Decimal("0"), BalanceDefaultDict(), {}, self.default_denomination),
                call(
                    sentinel.credit_limit,
                    sentinel.balances,
                    sentinel.supported_txn_types,
                    self.default_denomination,
                ),
            ]
        )
        mock_get_supported_txn_types.assert_called_once_with(mock_vault, None)
        mock_get_parameter.assert_called_once_with(
            name=credit_card.PARAM_CREDIT_LIMIT, vault=mock_vault
        )
        mock_get_overlimit_amount.assert_called_once_with(
            sentinel.balances,
            sentinel.credit_limit,
            self.default_denomination,
            sentinel.supported_txn_types,
        )

    @patch.object(credit_card.utils, "str_to_bool")
    @patch.object(credit_card, "_get_overlimit_amount")
    @patch.object(credit_card.utils, "get_parameter")
    @patch.object(credit_card, "_get_supported_txn_types")
    @patch.object(credit_card, "_get_available_balance")
    @patch.object(credit_card, "_update_balances")
    def test_account_has_insufficient_funds_rejection(
        self,
        mock_update_balances: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_get_supported_txn_types: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_overlimit_amount: MagicMock,
        mock_str_to_bool: MagicMock,
    ):
        # construct values
        def _update_balances_side_effect(
            account_id,
            balances,
            posting_instructions,
        ):
            balances.update(BalanceDefaultDict())

        available_balance_delta = Decimal("-1")
        available_balance = Decimal("0")

        # expected rejection
        expected_rejection = Rejection(
            message=f"Insufficient funds {self.default_denomination} {available_balance} for "
            f"{self.default_denomination} {-available_balance_delta} transaction "
            f"(excl advice instructions)",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )

        # construct mocks
        mock_vault = self.create_mock()
        mock_update_balances.side_effect = _update_balances_side_effect
        mock_get_available_balance.side_effect = [available_balance_delta, available_balance]
        mock_get_supported_txn_types.return_value = sentinel.supported_txn_types
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                credit_card.PARAM_CREDIT_LIMIT: sentinel.credit_limit,
                credit_card.PARAM_OVERLIMIT_OPT_IN: True,
                credit_card.PARAM_OVERLIMIT: Decimal("0"),
            }
        )
        mock_get_overlimit_amount.return_value = Decimal("0")
        mock_str_to_bool.return_value = True

        # run function
        result = credit_card._check_account_has_sufficient_funds(
            vault=mock_vault,
            balances=sentinel.balances,
            denomination=self.default_denomination,
            posting_instructions=[sentinel.posting_instruction],
        )
        self.assertEqual(expected_rejection, result)

        # assert calls
        mock_update_balances.assert_called_once_with(
            mock_vault.account_id,
            BalanceDefaultDict(),
            [sentinel.posting_instruction],
        )
        mock_get_available_balance.assert_has_calls(
            calls=[
                call(Decimal("0"), BalanceDefaultDict(), {}, self.default_denomination),
                call(
                    sentinel.credit_limit,
                    sentinel.balances,
                    sentinel.supported_txn_types,
                    self.default_denomination,
                ),
            ]
        )
        mock_get_supported_txn_types.assert_called_once_with(mock_vault, None)
        mock_get_parameter.assert_has_calls(
            calls=[
                call(name=credit_card.PARAM_CREDIT_LIMIT, vault=mock_vault),
                call(
                    mock_vault,
                    name=credit_card.PARAM_OVERLIMIT_OPT_IN,
                    is_optional=True,
                    is_boolean=True,
                    default_value="False",
                ),
                call(
                    mock_vault,
                    name=credit_card.PARAM_OVERLIMIT,
                    is_optional=True,
                    default_value=Decimal(0),
                ),
            ]
        )
        mock_get_overlimit_amount.assert_called_once_with(
            sentinel.balances,
            sentinel.credit_limit,
            self.default_denomination,
            sentinel.supported_txn_types,
        )

    @patch.object(credit_card.utils, "str_to_bool")
    @patch.object(credit_card, "_get_overlimit_amount")
    @patch.object(credit_card.utils, "get_parameter")
    @patch.object(credit_card, "_get_supported_txn_types")
    @patch.object(credit_card, "_get_available_balance")
    @patch.object(credit_card, "_update_balances")
    def test_account_has_sufficient_funds(
        self,
        mock_update_balances: MagicMock,
        mock_get_available_balance: MagicMock,
        mock_get_supported_txn_types: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_overlimit_amount: MagicMock,
        mock_str_to_bool: MagicMock,
    ):
        # construct values
        def _update_balances_side_effect(
            account_id,
            balances,
            posting_instructions,
        ):
            balances.update(BalanceDefaultDict())

        available_balance_delta = Decimal("-10")
        available_balance = Decimal("100")

        # construct mocks
        mock_vault = self.create_mock()
        mock_update_balances.side_effect = _update_balances_side_effect
        mock_get_available_balance.side_effect = [available_balance_delta, available_balance]
        mock_get_supported_txn_types.return_value = sentinel.supported_txn_types
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                credit_card.PARAM_CREDIT_LIMIT: sentinel.credit_limit,
                credit_card.PARAM_OVERLIMIT_OPT_IN: True,
                credit_card.PARAM_OVERLIMIT: Decimal("0"),
            }
        )
        mock_get_overlimit_amount.return_value = Decimal("0")
        mock_str_to_bool.return_value = True

        # run function with sufficuent funds
        result = credit_card._check_account_has_sufficient_funds(
            vault=mock_vault,
            balances=sentinel.balances,
            denomination=self.default_denomination,
            posting_instructions=[sentinel.posting_instruction],
        )
        self.assertIsNone(result)

        # assert calls
        mock_update_balances.assert_called_once_with(
            mock_vault.account_id,
            BalanceDefaultDict(),
            [sentinel.posting_instruction],
        )
        mock_get_available_balance.assert_has_calls(
            calls=[
                call(Decimal("0"), BalanceDefaultDict(), {}, self.default_denomination),
                call(
                    sentinel.credit_limit,
                    sentinel.balances,
                    sentinel.supported_txn_types,
                    self.default_denomination,
                ),
            ]
        )
        mock_get_supported_txn_types.assert_called_once_with(mock_vault, None)
        mock_get_parameter.assert_has_calls(
            calls=[
                call(name=credit_card.PARAM_CREDIT_LIMIT, vault=mock_vault),
                call(
                    mock_vault,
                    name=credit_card.PARAM_OVERLIMIT_OPT_IN,
                    is_optional=True,
                    is_boolean=True,
                    default_value="False",
                ),
                call(
                    mock_vault,
                    name=credit_card.PARAM_OVERLIMIT,
                    is_optional=True,
                    default_value=Decimal(0),
                ),
            ]
        )
        mock_get_overlimit_amount.assert_called_once_with(
            sentinel.balances,
            sentinel.credit_limit,
            self.default_denomination,
            sentinel.supported_txn_types,
        )


@patch.object(credit_card.utils, "round_decimal")
@patch.object(credit_card.utils, "balance_at_coordinates")
@patch.object(credit_card, "_get_overdue_balances")
@patch.object(credit_card, "_get_overlimit_amount")
class CalculatePercentageMadTest(CreditCardTestBase):
    def test_calculate_percentage_mad(
        self,
        mock_get_overlimit_amount: MagicMock,
        mock_get_overdue_balances: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_round_decimal: MagicMock,
    ):
        # construct values
        txn_types: dict[str, Optional[list[str]]] = {"TXN_TYPE": None}
        mad_percentages = {
            credit_card.INTEREST.lower(): Decimal("1.0"),
            credit_card.FEES.lower(): Decimal("0.5"),
            "txn_type": Decimal("0.05"),
        }

        # construct mocks
        mock_get_overlimit_amount.return_value = Decimal("0")
        mock_get_overdue_balances.return_value = {"OVERDUE_ADDRESS": Decimal("0")}
        mock_balance_at_coordinates.side_effect = [
            # principal coordinates
            Decimal("1"),
            Decimal("2"),
            # interest coordinates
            Decimal("3"),
            Decimal("4"),
            # fees coordinates
            Decimal("5"),
            Decimal("6"),
        ]
        mock_round_decimal.side_effect = [
            Decimal("0.15"),
            Decimal("7.00"),
            Decimal("5.50"),
        ]
        expected_result = Decimal("12.65")

        # run function
        result = credit_card._calculate_percentage_mad(
            in_flight_balances=sentinel.in_flight_balances,
            denomination=self.default_denomination,
            mad_percentages=mad_percentages,
            txn_types=txn_types,
            fee_types=["FEE_TYPE"],
            credit_limit=sentinel.credit_limit,
        )
        self.assertEqual(expected_result, result)

        # assert calls
        mock_get_overlimit_amount.assert_called_once_with(
            sentinel.in_flight_balances, sentinel.credit_limit, self.default_denomination, txn_types
        )
        mock_get_overdue_balances.assert_called_once_with(sentinel.in_flight_balances)
        mock_balance_at_coordinates.assert_has_calls(
            calls=[
                call(
                    balances=sentinel.in_flight_balances,
                    address="TXN_TYPE_UNPAID",
                    denomination=self.default_denomination,
                ),
                call(
                    balances=sentinel.in_flight_balances,
                    address="TXN_TYPE_BILLED",
                    denomination=self.default_denomination,
                ),
                call(
                    balances=sentinel.in_flight_balances,
                    address="TXN_TYPE_INTEREST_UNPAID",
                    denomination=self.default_denomination,
                ),
                call(
                    balances=sentinel.in_flight_balances,
                    address="TXN_TYPE_INTEREST_BILLED",
                    denomination=self.default_denomination,
                ),
                call(
                    balances=sentinel.in_flight_balances,
                    address="FEE_TYPES_UNPAID",
                    denomination=self.default_denomination,
                ),
                call(
                    balances=sentinel.in_flight_balances,
                    address="FEE_TYPES_BILLED",
                    denomination=self.default_denomination,
                ),
            ]
        )
        mock_round_decimal.assert_has_calls(
            calls=[
                # ( 1 + 2 ) * .05 = .15 <- principal_percentage
                call(Decimal("0.15"), 2),
                # ( 3 + 4 ) * 1.0 = 7.0 < -interest_percentage
                call(Decimal("7.0"), 2),
                # ( 5 + 6 ) * 0.5 = 5.5 < -fees_percentage
                call(Decimal("5.5"), 2),
            ]
        )


class ProcessRepaymentTest(CreditCardTestBase):
    @patch.object(credit_card, "_update_total_repayment_tracker")
    @patch.object(credit_card, "_make_deposit_postings")
    @patch.object(credit_card, "_repay_overdue_buckets")
    @patch.object(credit_card, "_repay_spend_and_charges")
    @patch.object(credit_card, "get_denomination_from_posting_instruction")
    @patch.object(credit_card, "_get_settlement_info")
    def test_process_repayment(
        self,
        mock_get_settlement_info: MagicMock,
        mock_get_denomination_from_posting_instruction: MagicMock,
        mock_repay_spend_and_charges: MagicMock,
        mock_repay_overdue_buckets: MagicMock,
        mock_make_deposit_postings: MagicMock,
        mock_update_total_repayment_tracker: MagicMock,
    ):
        # construct values
        repayment_posting_instructions = [
            SentinelCustomInstruction("repay_spend_charges"),
            SentinelCustomInstruction("repay_overdue_buckets"),
            SentinelCustomInstruction("make_deposit_postings"),
            SentinelCustomInstruction("update_total_repayment_tracker"),
        ]

        # construct mocks
        mock_get_settlement_info.return_value = Decimal("1"), sentinel._
        mock_get_denomination_from_posting_instruction.return_value = self.default_denomination

        def _repay_spend_and_charges_side_effect(
            vault,
            in_flight_balances,
            effective_datetime,
            repayment_posting_instructions,
            posting_instruction,
            remaining_repayment_amount,
        ):
            repayment_posting_instructions.extend(
                [SentinelCustomInstruction("repay_spend_charges")]
            )
            return Decimal("2")

        mock_repay_spend_and_charges.side_effect = _repay_spend_and_charges_side_effect

        def _repay_overdue_buckets_side_effect(
            vault,
            denomination,
            in_flight_balances,
            repayment_posting_instructions,
            repayment_amount,
        ):
            repayment_posting_instructions.extend(
                [SentinelCustomInstruction("repay_overdue_buckets")]
            )

        mock_repay_overdue_buckets.side_effect = _repay_overdue_buckets_side_effect

        mock_make_deposit_postings.return_value = [
            SentinelCustomInstruction("make_deposit_postings")
        ]
        mock_update_total_repayment_tracker.return_value = [
            SentinelCustomInstruction("update_total_repayment_tracker")
        ]

        # expected result
        expected_result = repayment_posting_instructions, sentinel.in_flight_balances

        # run function
        result = credit_card._process_repayment(
            vault=sentinel.vault,
            denomination=self.default_denomination,
            posting_instruction=sentinel.posting_instructions,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.assertEqual(expected_result, result)

        # call assertions
        mock_get_settlement_info.assert_called_once_with(
            sentinel.vault,
            self.default_denomination,
            sentinel.posting_instructions,
            None,
            account_id=None,
        )
        mock_get_denomination_from_posting_instruction.assert_called_once_with(
            sentinel.posting_instructions
        )
        mock_repay_spend_and_charges.assert_called_once_with(
            sentinel.vault,
            sentinel.in_flight_balances,
            DEFAULT_DATETIME,
            repayment_posting_instructions,
            sentinel.posting_instructions,
            Decimal("1"),  # total repayment amount
        )
        mock_repay_overdue_buckets.assert_called_once_with(
            sentinel.vault,
            self.default_denomination,
            sentinel.in_flight_balances,
            repayment_posting_instructions,
            Decimal("1"),  # total repayment amount
        )
        mock_make_deposit_postings.assert_called_once_with(
            sentinel.vault,
            self.default_denomination,
            Decimal("2"),  # remaining repayment amount
            sentinel.in_flight_balances,
            {},
            is_repayment=True,
        )
        mock_update_total_repayment_tracker.assert_called_once_with(
            sentinel.vault, sentinel.in_flight_balances, self.default_denomination, Decimal("1")
        )

    @patch.object(credit_card, "_get_settlement_info")
    def test_zero_total_repayment_amount(
        self,
        mock_get_settlement_info: MagicMock,
    ):
        # construct mocks
        mock_get_settlement_info.return_value = Decimal("0"), sentinel._

        # expected result
        expected_result: tuple[list[CustomInstruction], BalanceDefaultDict] = (
            [],
            sentinel.in_flight_balances,
        )

        # run function
        result = credit_card._process_repayment(
            vault=sentinel.vault,
            denomination=self.default_denomination,
            posting_instruction=sentinel.posting_instructions,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.assertEqual(expected_result, result)

        # call assertions
        mock_get_settlement_info.assert_called_once_with(
            sentinel.vault,
            self.default_denomination,
            sentinel.posting_instructions,
            None,
            account_id=None,
        )


class RebalancePostingsTest(CreditCardTestBase):
    @patch.object(credit_card, "_process_repayment")
    def test_standard_transaction_type_credit(
        self,
        mock_process_repayment: MagicMock,
    ):
        # construct values and mocks
        inbound_hard_settlement = self.inbound_hard_settlement(
            amount=Decimal("1"), client_transaction_id="IHS"
        )
        inbound_hard_settlement_id = "client_id_IHS"
        process_repayment_postings = [SentinelCustomInstruction("process_repayment")]
        mock_process_repayment.return_value = (
            process_repayment_postings,
            sentinel.in_flight_balances,
        )
        client_transactions: dict[str, ClientTransaction] = {
            inbound_hard_settlement_id: sentinel.inbound_hard_settlement,
        }

        # run function
        result = credit_card._rebalance_postings(
            vault=sentinel.vault,
            denomination=self.default_denomination,
            posting_instructions=[inbound_hard_settlement],
            client_transactions=client_transactions,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.assertEqual(process_repayment_postings, result)

        # call assertions
        mock_process_repayment.assert_called_once_with(
            sentinel.vault,
            self.default_denomination,
            inbound_hard_settlement,
            sentinel.in_flight_balances,
            DEFAULT_DATETIME,
            sentinel.inbound_hard_settlement,
        )

    @patch.object(credit_card, "_rebalance_outbound_settlement")
    def test_standard_transaction_type_debit(
        self,
        mock_rebalance_outbound_settlement: MagicMock,
    ):
        # construct values and mocks
        outbound_hard_settlement = self.outbound_hard_settlement(
            amount=Decimal("2"), client_transaction_id="OHS"
        )
        outbound_hard_settlement_id = "client_id_OHS"
        rebalance_settlement_postings = [SentinelCustomInstruction("rebalance_settlement")]
        mock_rebalance_outbound_settlement.return_value = rebalance_settlement_postings
        client_transactions: dict[str, ClientTransaction] = {
            outbound_hard_settlement_id: sentinel.outbound_hard_settlement_txn,
        }

        # run function
        result = credit_card._rebalance_postings(
            vault=sentinel.vault,
            denomination=self.default_denomination,
            posting_instructions=[outbound_hard_settlement],
            client_transactions=client_transactions,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.assertEqual(rebalance_settlement_postings, result)

        # call assertions
        mock_rebalance_outbound_settlement.assert_called_once_with(
            vault=sentinel.vault,
            client_transaction=sentinel.outbound_hard_settlement_txn,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
        )

    @patch.object(credit_card, "_rebalance_outbound_auth")
    def test_outbound_authorisation(
        self,
        mock_rebalance_outbound_auth: MagicMock,
    ):
        # construct values and mocks
        outbound_auth = self.outbound_auth(amount=Decimal("3"), client_transaction_id="OA")
        outbound_auth_id = "client_id_OA"
        rebalance_outbound_auth_postings = [SentinelCustomInstruction("rebalance_outbound_auth")]
        mock_rebalance_outbound_auth.return_value = rebalance_outbound_auth_postings
        client_transactions: dict[str, ClientTransaction] = {
            outbound_auth_id: sentinel.outbound_auth_txn,
        }

        # run function
        result = credit_card._rebalance_postings(
            vault=sentinel.vault,
            denomination=self.default_denomination,
            posting_instructions=[outbound_auth],
            client_transactions=client_transactions,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.assertEqual(rebalance_outbound_auth_postings, result)

        # call assertions
        mock_rebalance_outbound_auth.assert_called_once_with(
            sentinel.vault,
            self.default_denomination,
            outbound_auth,
            sentinel.in_flight_balances,
            DEFAULT_DATETIME,
        )

    @patch.object(credit_card, "_rebalance_auth_adjust")
    def test_authorisation_adjustment(
        self,
        mock_rebalance_auth_adjust: MagicMock,
    ):
        # construct values and mocks
        auth_adjust = self.inbound_auth_adjust(amount=Decimal("4"), client_transaction_id="AA")
        auth_adjust_id = "client_id_AA"
        rebalance_auth_adjust_postings = [SentinelCustomInstruction("rebalance_auth_adjust")]
        mock_rebalance_auth_adjust.return_value = rebalance_auth_adjust_postings
        client_transactions: dict[str, ClientTransaction] = {
            auth_adjust_id: sentinel.auth_adjust_txn,
        }

        # run function
        result = credit_card._rebalance_postings(
            vault=sentinel.vault,
            denomination=self.default_denomination,
            posting_instructions=[auth_adjust],
            client_transactions=client_transactions,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.assertEqual(rebalance_auth_adjust_postings, result)

        # call assertions
        mock_rebalance_auth_adjust.assert_called_once_with(
            sentinel.vault,
            self.default_denomination,
            auth_adjust,
            sentinel.in_flight_balances,
            DEFAULT_DATETIME,
        )

    @patch.object(credit_card, "_rebalance_release")
    def test_release(
        self,
        mock_rebalance_release: MagicMock,
    ):
        # construct values and mocks
        release = self.release_outbound_auth(
            unsettled_amount=Decimal("5"), client_transaction_id="R"
        )
        release_id = "client_id_R"
        rebalance_release_postings = [SentinelCustomInstruction("rebalance_release")]
        mock_rebalance_release.return_value = rebalance_release_postings
        client_transactions: dict[str, ClientTransaction] = {
            release_id: sentinel.release_txn,
        }

        # run function
        result = credit_card._rebalance_postings(
            vault=sentinel.vault,
            denomination=self.default_denomination,
            posting_instructions=[release],
            client_transactions=client_transactions,
            in_flight_balances=sentinel.in_flight_balances,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.assertEqual(rebalance_release_postings, result)

        # call assertions
        mock_rebalance_release.assert_called_once_with(
            sentinel.vault,
            self.default_denomination,
            release,
            sentinel.release_txn,
            sentinel.in_flight_balances,
            DEFAULT_DATETIME,
        )


class GetBalancesToAccrueOnTest(CreditCardTestBase):
    @patch.object(credit_card, "_set_accruals_by_sub_type")
    @patch.object(credit_card, "_is_revolver")
    @patch.object(credit_card, "_is_txn_type_in_interest_free_period")
    @patch.object(credit_card, "_fee_address")
    @patch.object(credit_card, "_interest_address")
    @patch.object(credit_card, "_principal_address")
    @patch.object(credit_card, "_get_outstanding_statement_amount")
    def test_get_balances_to_accrue_on(
        self,
        mock_get_outstanding_statement_amount: MagicMock,
        mock_principal_address: MagicMock,
        mock_interest_address: MagicMock,
        mock_fee_address: MagicMock,
        mock_is_txn_type_in_interest_free_period: MagicMock,
        mock_is_revolver: MagicMock,
        mock_set_accruals_by_sub_type: MagicMock,
    ):
        # construct values
        accrue_interest_from_txn_day = True
        balances = BalanceDefaultDict(
            mapping={
                self.balance_coordinate(
                    account_address="PRINCIPAL_ADDRESS_BILLED", denomination="GBP"
                ): self.balance(debit=Decimal("100"), credit=Decimal("0")),
                self.balance_coordinate(
                    account_address="PRINCIPAL_ADDRESS_CHARGED", denomination="GBP"
                ): self.balance(debit=Decimal("0"), credit=Decimal("0")),
                # no interest balance to accrue on. This handles the case of:
                # if amount_to_accrue_on == Decimal(0):
                self.balance_coordinate(
                    account_address="INTEREST_ADDRESS_BILLED", denomination="GBP"
                ): self.balance(debit=Decimal("0"), credit=Decimal("0")),
                self.balance_coordinate(
                    account_address="FEE_ADDRESS", denomination="GBP"
                ): self.balance(debit=Decimal("5"), credit=Decimal("0")),
            }
        )
        supported_txn_types: dict[str, Optional[list[str]]] = {"TEST": None}
        supported_fee_types = ["FEE"]
        txn_types_to_charge_interest_from_txn_date: list[str] = []

        expected_result_post = {("PRINCIPAL", "TEST", "POST_SCOD"): {"": Decimal("0.00")}}
        expected_result_pre = {("PRINCIPAL", "TEST", "PRE_SCOD"): {"": Decimal("0.00")}}
        expected_result_none = {("FEES", "FEE", ""): {"": Decimal("0.00")}}

        def _set_accruals_by_sub_type_side_effect(
            accruals_by_sub_type,
            charge_type,
            sub_type,
            ref,
            accrual_amount,
            accrual_type=None,
        ):
            if accrual_type == credit_card.POST_SCOD:
                accruals_by_sub_type.update(expected_result_post)
            elif accrual_type == credit_card.PRE_SCOD:
                accruals_by_sub_type.update(expected_result_pre)
            elif accrual_type is None:
                accruals_by_sub_type.update(expected_result_none)

        mock_set_accruals_by_sub_type.side_effect = _set_accruals_by_sub_type_side_effect

        # expected result
        expected_result = {
            **expected_result_post,
            **expected_result_pre,
            **expected_result_none,
        }

        # construct mocks
        mock_get_outstanding_statement_amount.return_value = Decimal("1000")
        mock_principal_address.side_effect = [
            "PRINCIPAL_ADDRESS_BILLED",
            "PRINCIPAL_ADDRESS_CHARGED",
            "PRINCIPAL_ADDRESS_UNPAID",
        ]
        mock_interest_address.side_effect = ["INTEREST_ADDRESS_BILLED"]
        mock_fee_address.side_effect = ["FEE_ADDRESS"]
        mock_is_txn_type_in_interest_free_period.side_effect = [False, False]
        mock_is_revolver.side_effect = [False, False]

        # run function
        result = credit_card._get_balances_to_accrue_on(
            balances=balances,
            denomination=self.default_denomination,
            supported_fee_types=supported_fee_types,
            supported_txn_types=supported_txn_types,
            txn_types_to_charge_interest_from_txn_date=txn_types_to_charge_interest_from_txn_date,
            accrue_interest_from_txn_day=accrue_interest_from_txn_day,
            accrue_interest_on_unpaid_interest=True,
            accrue_interest_on_unpaid_fees=True,
            txn_types_in_interest_free_period=sentinel.txn_types_in_interest_free_period,
        )
        self.assertEqual(expected_result, result)

        # call assertions
        mock_get_outstanding_statement_amount.assert_called_once_with(
            balances, self.default_denomination, supported_fee_types, supported_txn_types
        )
        mock_is_revolver.assert_has_calls(
            calls=[
                call(balances, self.default_denomination),
                call(balances, self.default_denomination),
            ]
        )
        mock_is_txn_type_in_interest_free_period.assert_has_calls(
            calls=[
                call(sentinel.txn_types_in_interest_free_period, "TEST", ""),
                call(sentinel.txn_types_in_interest_free_period, "TEST", ""),
            ]
        )
        mock_principal_address.assert_has_calls(
            calls=[
                call("TEST", "BILLED", txn_ref=""),
                call("TEST", "CHARGED", txn_ref=""),
                call("TEST", "UNPAID", txn_ref=""),
            ]
        )
        mock_interest_address.assert_called_once_with("TEST", "UNPAID", txn_ref="")
        mock_fee_address.assert_called_once_with("FEE", "UNPAID")
        mock_set_accruals_by_sub_type.assert_has_calls(
            calls=[
                call(
                    ANY,  # balances to accrue on
                    charge_type="PRINCIPAL",
                    sub_type="TEST",
                    accrual_amount=Decimal("100"),
                    ref="",
                    accrual_type=credit_card.POST_SCOD,
                ),
                call(
                    ANY,  # balances to accrue on
                    charge_type="PRINCIPAL",
                    sub_type="TEST",
                    accrual_amount=Decimal("0"),
                    ref="",
                    accrual_type=credit_card.PRE_SCOD,
                ),
                call(
                    ANY,  # balances to accrue on
                    charge_type="FEES",
                    sub_type="FEE",
                    accrual_amount=Decimal("5"),
                    ref=None,
                ),
            ]
        )


class ProcessPaymentDueDateTest(CreditCardTestBase):
    @patch.object(credit_card, "_is_revolver")
    @patch.object(credit_card, "_reverse_uncharged_interest")
    @patch.object(credit_card, "_get_outstanding_statement_amount")
    @patch.object(credit_card, "_is_txn_interest_accrual_from_txn_day")
    @patch.object(credit_card, "_get_supported_fee_types")
    @patch.object(credit_card, "_get_supported_txn_types")
    @patch.object(credit_card, "_deep_copy_balances")
    @patch.object(credit_card.utils, "get_parameter")
    def test_outstanding_statement_balance_zero_and_non_revolver_and_accrue_interest_from_txn_day(
        self,
        mock_get_parameter: MagicMock,
        mock_deep_copy_balances: MagicMock,
        mock_get_supported_txn_types: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_is_txn_interest_accrual_from_txn_day: MagicMock,
        mock_get_outstanding_statement_amount: MagicMock,
        mock_reverse_uncharged_interest: MagicMock,
        mock_is_revolver: MagicMock,
    ):
        # construct values
        live_balances = BalanceDefaultDict(mapping={DEFAULT_COORDINATE: Balance(net=Decimal("0"))})

        supported_txn_types = {"TXN_TYPE": None}
        bof_mapping = {
            credit_card.fetchers.LIVE_BALANCES_BOF_ID: BalancesObservation(balances=live_balances)
        }
        instructions: list[CustomInstruction] = [
            SentinelCustomInstruction("REVERSE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED"),
            SentinelCustomInstruction("OUTSTANDING_REPAID"),
        ]

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "credit_limit": sentinel.credit_limit,
            }
        )
        mock_vault = self.create_mock(balances_observation_fetchers_mapping=bof_mapping)
        mock_deep_copy_balances.return_value = sentinel.in_flight_balances
        mock_get_supported_txn_types.return_value = supported_txn_types
        mock_get_supported_fee_types.return_value = sentinel.supported_fee_types
        mock_is_txn_interest_accrual_from_txn_day.return_value = True
        mock_get_outstanding_statement_amount.return_value = Decimal("0")
        mock_reverse_uncharged_interest.side_effect = [[instructions[0]], [instructions[1]]]
        mock_is_revolver.return_value = False

        # expected result
        expected_result: tuple[
            list[PostingInstructionsDirective], list[AccountNotificationDirective]
        ] = [
            PostingInstructionsDirective(
                posting_instructions=instructions,
                client_batch_id=f"ZERO_OUT_ACCRUED_INTEREST-{mock_vault.get_hook_execution_id()}",
            ),
        ], []

        # run function
        result = credit_card._process_payment_due_date(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )
        self.assertEqual(expected_result, result)

        # call assertions
        mock_reverse_uncharged_interest.assert_has_calls(
            calls=[
                call(
                    mock_vault,
                    sentinel.in_flight_balances,
                    sentinel.denomination,
                    {"TXN_TYPE_INTEREST_FREE_PERIOD": None},
                    "REVERSE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED",
                ),
                call(
                    mock_vault,
                    sentinel.in_flight_balances,
                    sentinel.denomination,
                    supported_txn_types,
                    "OUTSTANDING_REPAID",
                    credit_card.POST_SCOD,
                ),
            ]
        )

    @patch.object(credit_card, "_is_revolver")
    @patch.object(credit_card, "_reverse_uncharged_interest")
    @patch.object(credit_card, "_get_outstanding_statement_amount")
    @patch.object(credit_card, "_is_txn_interest_accrual_from_txn_day")
    @patch.object(credit_card, "_get_supported_fee_types")
    @patch.object(credit_card, "_get_supported_txn_types")
    @patch.object(credit_card, "_deep_copy_balances")
    @patch.object(credit_card.utils, "get_parameter")
    def test_outstanding_statement_balance_zero_and_non_revolver_not_accrue_interest_from_txn_day(
        self,
        mock_get_parameter: MagicMock,
        mock_deep_copy_balances: MagicMock,
        mock_get_supported_txn_types: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_is_txn_interest_accrual_from_txn_day: MagicMock,
        mock_get_outstanding_statement_amount: MagicMock,
        mock_reverse_uncharged_interest: MagicMock,
        mock_is_revolver: MagicMock,
    ):
        # construct mocks
        bof_mapping = {
            credit_card.fetchers.LIVE_BALANCES_BOF_ID: BalancesObservation(
                balances=BalanceDefaultDict()
            )
        }
        supported_txn_types = {"TXN_TYPE": None}
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "credit_limit": sentinel.credit_limit,
            }
        )
        mock_vault = self.create_mock(balances_observation_fetchers_mapping=bof_mapping)
        mock_deep_copy_balances.return_value = sentinel.in_flight_balances
        mock_get_supported_txn_types.return_value = supported_txn_types
        mock_get_supported_fee_types.return_value = sentinel.supported_fee_types
        mock_is_txn_interest_accrual_from_txn_day.return_value = False
        mock_get_outstanding_statement_amount.return_value = Decimal("0")
        mock_reverse_uncharged_interest.side_effect = [[], []]
        mock_is_revolver.return_value = False

        # expected result
        expected_result: tuple[
            list[PostingInstructionsDirective], list[AccountNotificationDirective]
        ] = ([], [])

        # run function
        result = credit_card._process_payment_due_date(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )
        self.assertEqual(expected_result, result)

        # call assertions
        mock_reverse_uncharged_interest.assert_has_calls(
            calls=[
                call(
                    mock_vault,
                    sentinel.in_flight_balances,
                    sentinel.denomination,
                    {"TXN_TYPE_INTEREST_FREE_PERIOD": None},
                    "REVERSE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED",
                ),
                call(
                    mock_vault,
                    sentinel.in_flight_balances,
                    sentinel.denomination,
                    supported_txn_types,
                    "OUTSTANDING_REPAID",
                ),
            ]
        )

    @patch.object(credit_card, "_move_outstanding_statement")
    @patch.object(credit_card, "_adjust_aggregate_balances")
    @patch.object(credit_card, "_zero_out_mad_balance")
    @patch.object(credit_card.utils, "is_flag_in_list_applied")
    @patch.object(credit_card.utils, "balance_at_coordinates")
    @patch.object(credit_card, "_charge_interest")
    @patch.object(credit_card, "_set_accruals_by_sub_type")
    @patch.object(credit_card, "_get_txn_type_and_ref_debit_address")
    @patch.object(credit_card, "_change_revolver_status")
    @patch.object(credit_card, "_is_revolver")
    @patch.object(credit_card, "_reverse_uncharged_interest")
    @patch.object(credit_card, "_get_outstanding_statement_amount")
    @patch.object(credit_card, "_is_txn_interest_accrual_from_txn_day")
    @patch.object(credit_card, "_get_supported_fee_types")
    @patch.object(credit_card, "_get_supported_txn_types")
    @patch.object(credit_card.utils, "get_parameter")
    def test_outstanding_statement_balance_non_zero_and_non_revolver(
        self,
        mock_get_parameter: MagicMock,
        mock_get_supported_txn_types: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_is_txn_interest_accrual_from_txn_day: MagicMock,
        mock_get_outstanding_statement_amount: MagicMock,
        mock_reverse_uncharged_interest: MagicMock,
        mock_is_revolver: MagicMock,
        mock_change_revolver_status: MagicMock,
        mock_get_txn_type_and_ref_debit_address: MagicMock,
        mock_set_accruals_by_sub_type: MagicMock,
        mock_charge_interest: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_zero_out_mad_balance: MagicMock,
        mock_adjust_aggregate_balances: MagicMock,
        mock_move_outstanding_statement: MagicMock,
    ):
        # construct values
        live_balances = BalanceDefaultDict(
            mapping={
                DEFAULT_COORDINATE: Balance(net=Decimal("1")),
                self.balance_coordinate(
                    account_address=(
                        f"TEST_{credit_card.INTEREST_FREE_PERIOD_UNCHARGED_INTEREST_BALANCE}"
                    ),
                    denomination=self.default_denomination,
                ): Balance(net=Decimal("0")),
                self.balance_coordinate(
                    account_address=f"TEST_PRE_SCOD_{credit_card.UNCHARGED}",
                    denomination=self.default_denomination,
                ): Balance(net=Decimal("0")),
            }
        )

        supported_txn_types = {"TXN_TYPE": None}
        bof_mapping = {
            credit_card.fetchers.LIVE_BALANCES_BOF_ID: BalancesObservation(balances=live_balances)
        }
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "credit_limit": sentinel.credit_limit,
            }
        )
        mock_vault = self.create_mock(balances_observation_fetchers_mapping=bof_mapping)
        mock_get_supported_txn_types.return_value = supported_txn_types
        mock_get_supported_fee_types.return_value = sentinel.supported_fee_types
        mock_is_txn_interest_accrual_from_txn_day.return_value = True
        mock_get_outstanding_statement_amount.return_value = Decimal("1")
        mock_reverse_uncharged_interest.return_value = []
        mock_is_revolver.return_value = False
        mock_change_revolver_status.return_value = [
            SentinelCustomInstruction("change_revolver_status")
        ]
        mock_get_txn_type_and_ref_debit_address.return_value = sentinel.sub_type, sentinel.ref

        def _set_accruals_by_sub_type_side_effect(
            accruals_by_sub_type,
            charge_type,
            sub_type,
            accrual_amount,
            ref,
            accrual_type,
        ):
            accruals_by_sub_type.update({("", "", ""): {"": Decimal("0")}})

        mock_set_accruals_by_sub_type.side_effect = _set_accruals_by_sub_type_side_effect

        def _charge_interest_side_effect(
            vault,
            is_revolver,
            denomination,
            accruals_by_sub_type,
            txn_types_to_charge_interest_from_txn_date,
            in_flight_balances,
            instructions,
            is_pdd,
        ):
            instructions.extend([SentinelCustomInstruction("charge_interest")])

        mock_charge_interest.side_effect = _charge_interest_side_effect
        mock_balance_at_coordinates.side_effect = [Decimal("100"), Decimal("9")]
        mock_is_flag_in_list_applied.return_value = True
        mock_zero_out_mad_balance.return_value = [SentinelCustomInstruction("zero_out_mad_balance")]
        mock_adjust_aggregate_balances.return_value = [
            SentinelCustomInstruction("adjust_aggregate_balances")
        ]
        mock_move_outstanding_statement.return_value = [
            SentinelCustomInstruction("move_outstanding_statement")
        ]

        # expected result
        instructions: list[CustomInstruction] = [
            SentinelCustomInstruction("change_revolver_status"),
            SentinelCustomInstruction("charge_interest"),
            SentinelCustomInstruction("zero_out_mad_balance"),
            SentinelCustomInstruction("adjust_aggregate_balances"),
            SentinelCustomInstruction("move_outstanding_statement"),
        ]
        expected_result: tuple[
            list[PostingInstructionsDirective], list[AccountNotificationDirective]
        ] = (
            [
                PostingInstructionsDirective(
                    posting_instructions=instructions,
                    client_batch_id=f"PDD-{mock_vault.get_hook_execution_id()}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            [],
        )

        # run function
        result = credit_card._process_payment_due_date(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )
        self.assertEqual(expected_result, result)

        # call assertions
        mock_reverse_uncharged_interest.assert_called_once_with(
            mock_vault,
            live_balances,
            sentinel.denomination,
            {"TXN_TYPE_INTEREST_FREE_PERIOD": None},
            "REVERSE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED",
        )
        mock_change_revolver_status.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            live_balances,
            revolver=True,
        )
        mock_set_accruals_by_sub_type.assert_called_once_with(
            {("", "", ""): {"": Decimal("0")}},  # accruals by sub type
            charge_type=credit_card.PRINCIPAL,
            sub_type=sentinel.sub_type,
            accrual_amount=Decimal("0"),
            ref=sentinel.ref,
            accrual_type="PRE_SCOD",
        )
        mock_charge_interest.assert_called_once_with(
            mock_vault,
            is_revolver=True,
            denomination=sentinel.denomination,
            accruals_by_sub_type={("", "", ""): {"": Decimal("0")}},  # accruals by sub type,
            txn_types_to_charge_interest_from_txn_date=[],
            in_flight_balances=live_balances,
            instructions=instructions,
            is_pdd=True,
        )
        mock_zero_out_mad_balance.assert_called_once_with(
            mock_vault, Decimal("9"), sentinel.denomination
        )
        mock_adjust_aggregate_balances.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            live_balances,
            effective_datetime=DEFAULT_DATETIME,
            credit_limit=sentinel.credit_limit,
        )
        mock_move_outstanding_statement.assert_called_once_with(
            mock_vault,
            live_balances,
            sentinel.denomination,
            Decimal("0"),  # new overdue amount
            supported_txn_types,
            DEFAULT_DATETIME,
        )

    @patch.object(credit_card, "_move_outstanding_statement")
    @patch.object(credit_card, "_adjust_aggregate_balances")
    @patch.object(credit_card, "_zero_out_mad_balance")
    @patch.object(credit_card.utils, "is_flag_in_list_applied")
    @patch.object(credit_card.utils, "balance_at_coordinates")
    @patch.object(credit_card, "_charge_interest")
    @patch.object(credit_card, "_set_accruals_by_sub_type")
    @patch.object(credit_card, "_get_txn_type_and_ref_debit_address")
    @patch.object(credit_card, "_change_revolver_status")
    @patch.object(credit_card, "_is_revolver")
    @patch.object(credit_card, "_reverse_uncharged_interest")
    @patch.object(credit_card, "_get_outstanding_statement_amount")
    @patch.object(credit_card, "_is_txn_interest_accrual_from_txn_day")
    @patch.object(credit_card, "_get_supported_fee_types")
    @patch.object(credit_card, "_get_supported_txn_types")
    @patch.object(credit_card.utils, "get_parameter")
    def test_non_revolver_and_txn_interest_accrual_from_txn_day_false(
        self,
        mock_get_parameter: MagicMock,
        mock_get_supported_txn_types: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_is_txn_interest_accrual_from_txn_day: MagicMock,
        mock_get_outstanding_statement_amount: MagicMock,
        mock_reverse_uncharged_interest: MagicMock,
        mock_is_revolver: MagicMock,
        mock_change_revolver_status: MagicMock,
        mock_get_txn_type_and_ref_debit_address: MagicMock,
        mock_set_accruals_by_sub_type: MagicMock,
        mock_charge_interest: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_zero_out_mad_balance: MagicMock,
        mock_adjust_aggregate_balances: MagicMock,
        mock_move_outstanding_statement: MagicMock,
    ):
        # construct values
        live_balances = BalanceDefaultDict(
            mapping={
                DEFAULT_COORDINATE: Balance(net=Decimal("1")),
                self.balance_coordinate(
                    account_address=(
                        f"TEST_{credit_card.INTEREST_FREE_PERIOD_UNCHARGED_INTEREST_BALANCE}"
                    ),
                    denomination=self.default_denomination,
                ): Balance(net=Decimal("0")),
                self.balance_coordinate(
                    account_address=f"TEST_PRE_SCOD_{credit_card.UNCHARGED}",
                    denomination=self.default_denomination,
                ): Balance(net=Decimal("0")),
            }
        )

        supported_txn_types = {"TXN_TYPE": None}
        bof_mapping = {
            credit_card.fetchers.LIVE_BALANCES_BOF_ID: BalancesObservation(balances=live_balances)
        }

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "credit_limit": sentinel.credit_limit,
            }
        )
        mock_vault = self.create_mock(balances_observation_fetchers_mapping=bof_mapping)
        mock_get_supported_txn_types.return_value = supported_txn_types
        mock_get_supported_fee_types.return_value = sentinel.supported_fee_types
        mock_is_txn_interest_accrual_from_txn_day.return_value = False
        mock_get_outstanding_statement_amount.return_value = Decimal("1")
        mock_reverse_uncharged_interest.return_value = []
        mock_is_revolver.return_value = False
        mock_change_revolver_status.return_value = [
            SentinelCustomInstruction("change_revolver_status")
        ]
        mock_get_txn_type_and_ref_debit_address.return_value = sentinel.sub_type, sentinel.ref

        def _set_accruals_by_sub_type_side_effect(
            accruals_by_sub_type,
            charge_type,
            sub_type,
            accrual_amount,
            ref,
        ):
            accruals_by_sub_type.update({("", "", ""): {"": Decimal("0")}})

        mock_set_accruals_by_sub_type.side_effect = _set_accruals_by_sub_type_side_effect

        def _charge_interest_side_effect(
            vault,
            is_revolver,
            denomination,
            accruals_by_sub_type,
            txn_types_to_charge_interest_from_txn_date,
            in_flight_balances,
            instructions,
            is_pdd,
        ):
            instructions.extend([SentinelCustomInstruction("charge_interest")])

        mock_charge_interest.side_effect = _charge_interest_side_effect
        mock_balance_at_coordinates.side_effect = [Decimal("100"), Decimal("9")]
        mock_is_flag_in_list_applied.return_value = True
        mock_zero_out_mad_balance.return_value = [SentinelCustomInstruction("zero_out_mad_balance")]
        mock_adjust_aggregate_balances.return_value = [
            SentinelCustomInstruction("adjust_aggregate_balances")
        ]
        mock_move_outstanding_statement.return_value = [
            SentinelCustomInstruction("move_outstanding_statement")
        ]

        # expected result
        instructions: list[CustomInstruction] = [
            SentinelCustomInstruction("change_revolver_status"),
            SentinelCustomInstruction("charge_interest"),
            SentinelCustomInstruction("zero_out_mad_balance"),
            SentinelCustomInstruction("adjust_aggregate_balances"),
            SentinelCustomInstruction("move_outstanding_statement"),
        ]
        expected_result: tuple[
            list[PostingInstructionsDirective], list[AccountNotificationDirective]
        ] = (
            [
                PostingInstructionsDirective(
                    posting_instructions=instructions,
                    client_batch_id=f"PDD-{mock_vault.get_hook_execution_id()}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            [],
        )

        # run function
        result = credit_card._process_payment_due_date(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )
        self.assertEqual(expected_result, result)

        # call assertions
        mock_reverse_uncharged_interest.assert_called_once_with(
            mock_vault,
            live_balances,
            sentinel.denomination,
            {"TXN_TYPE_INTEREST_FREE_PERIOD": None},
            "REVERSE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED",
        )
        mock_change_revolver_status.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            live_balances,
            revolver=True,
        )
        mock_set_accruals_by_sub_type.assert_called_once_with(
            {("", "", ""): {"": Decimal("0")}},  # accruals by sub type
            charge_type=credit_card.PRINCIPAL,
            sub_type=sentinel.sub_type,
            accrual_amount=Decimal("0"),
            ref=sentinel.ref,
        )
        mock_charge_interest.assert_called_once_with(
            mock_vault,
            is_revolver=True,
            denomination=sentinel.denomination,
            accruals_by_sub_type={("", "", ""): {"": Decimal("0")}},  # accruals by sub type,
            txn_types_to_charge_interest_from_txn_date=[],
            in_flight_balances=live_balances,
            instructions=instructions,
            is_pdd=True,
        )
        mock_zero_out_mad_balance.assert_called_once_with(
            mock_vault, Decimal("9"), sentinel.denomination
        )
        mock_adjust_aggregate_balances.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            live_balances,
            effective_datetime=DEFAULT_DATETIME,
            credit_limit=sentinel.credit_limit,
        )
        mock_move_outstanding_statement.assert_called_once_with(
            mock_vault,
            live_balances,
            sentinel.denomination,
            Decimal("0"),  # new overdue amount
            supported_txn_types,
            DEFAULT_DATETIME,
        )

    @patch.object(credit_card, "_move_outstanding_statement")
    @patch.object(credit_card, "_adjust_aggregate_balances")
    @patch.object(credit_card, "_charge_fee")
    @patch.object(credit_card, "_get_overdue_balances")
    @patch.object(credit_card.utils, "is_flag_in_list_applied")
    @patch.object(credit_card.utils, "balance_at_coordinates")
    @patch.object(credit_card, "_charge_interest")
    @patch.object(credit_card, "_set_accruals_by_sub_type")
    @patch.object(credit_card, "_get_txn_type_and_ref_debit_address")
    @patch.object(credit_card, "_is_revolver")
    @patch.object(credit_card, "_reverse_uncharged_interest")
    @patch.object(credit_card, "_get_outstanding_statement_amount")
    @patch.object(credit_card, "_is_txn_interest_accrual_from_txn_day")
    @patch.object(credit_card, "_get_supported_fee_types")
    @patch.object(credit_card, "_get_supported_txn_types")
    @patch.object(credit_card.utils, "get_parameter")
    def test_mad_greater_than_repayments(
        self,
        mock_get_parameter: MagicMock,
        mock_get_supported_txn_types: MagicMock,
        mock_get_supported_fee_types: MagicMock,
        mock_is_txn_interest_accrual_from_txn_day: MagicMock,
        mock_get_outstanding_statement_amount: MagicMock,
        mock_reverse_uncharged_interest: MagicMock,
        mock_is_revolver: MagicMock,
        mock_get_txn_type_and_ref_debit_address: MagicMock,
        mock_set_accruals_by_sub_type: MagicMock,
        mock_charge_interest: MagicMock,
        mock_balance_at_coordinates: MagicMock,
        mock_is_flag_in_list_applied: MagicMock,
        mock_get_overdue_balances: MagicMock,
        mock_charge_fee: MagicMock,
        mock_adjust_aggregate_balances: MagicMock,
        mock_move_outstanding_statement: MagicMock,
    ):
        # construct values
        live_balances = BalanceDefaultDict(
            mapping={
                DEFAULT_COORDINATE: Balance(net=Decimal("1")),
                self.balance_coordinate(
                    account_address=(
                        f"TEST_{credit_card.INTEREST_FREE_PERIOD_UNCHARGED_INTEREST_BALANCE}"
                    ),
                    denomination=self.default_denomination,
                ): Balance(net=Decimal("0")),
                self.balance_coordinate(
                    account_address=f"TEST_PRE_SCOD_{credit_card.UNCHARGED}",
                    denomination=self.default_denomination,
                ): Balance(net=Decimal("0")),
            }
        )

        supported_txn_types = {"TXN_TYPE": None}
        bof_mapping = {
            credit_card.fetchers.LIVE_BALANCES_BOF_ID: BalancesObservation(balances=live_balances)
        }

        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "denomination": sentinel.denomination,
                "credit_limit": sentinel.credit_limit,
            }
        )
        mock_vault = self.create_mock(balances_observation_fetchers_mapping=bof_mapping)
        mock_get_supported_txn_types.return_value = supported_txn_types
        mock_get_supported_fee_types.return_value = sentinel.supported_fee_types
        mock_is_txn_interest_accrual_from_txn_day.return_value = False
        mock_get_outstanding_statement_amount.return_value = Decimal("1")
        mock_reverse_uncharged_interest.return_value = []
        mock_is_revolver.return_value = True
        mock_get_txn_type_and_ref_debit_address.return_value = sentinel.sub_type, sentinel.ref

        def _set_accruals_by_sub_type_side_effect(
            accruals_by_sub_type,
            charge_type,
            sub_type,
            accrual_amount,
            ref,
        ):
            accruals_by_sub_type.update({("", "", ""): {"": Decimal("0")}})

        mock_set_accruals_by_sub_type.side_effect = _set_accruals_by_sub_type_side_effect

        def _charge_interest_side_effect(
            vault,
            is_revolver,
            denomination,
            accruals_by_sub_type,
            txn_types_to_charge_interest_from_txn_date,
            in_flight_balances,
            instructions,
            is_pdd,
            charge_interest_free_period,
        ):
            instructions.extend([SentinelCustomInstruction("charge_interest")])

        mock_charge_interest.side_effect = _charge_interest_side_effect
        mock_balance_at_coordinates.side_effect = [Decimal("10"), Decimal("100")]
        mock_is_flag_in_list_applied.return_value = False
        mock_get_overdue_balances.return_value = {"overdue": Decimal("90")}
        mock_charge_fee.return_value = (sentinel._, [SentinelCustomInstruction("charge_fee")])
        mock_adjust_aggregate_balances.return_value = [
            SentinelCustomInstruction("adjust_aggregate_balances")
        ]
        mock_move_outstanding_statement.return_value = [
            SentinelCustomInstruction("move_outstanding_statement")
        ]

        # expected result
        instructions: list[CustomInstruction] = [
            SentinelCustomInstruction("charge_fee"),
            SentinelCustomInstruction("charge_interest"),
            SentinelCustomInstruction("adjust_aggregate_balances"),
            SentinelCustomInstruction("move_outstanding_statement"),
        ]
        expected_result: tuple[
            list[PostingInstructionsDirective], list[AccountNotificationDirective]
        ] = (
            [
                PostingInstructionsDirective(
                    posting_instructions=instructions,
                    client_batch_id=f"PDD-{mock_vault.get_hook_execution_id()}",
                    value_datetime=DEFAULT_DATETIME,
                )
            ],
            [
                AccountNotificationDirective(
                    notification_type=credit_card.EXPIRE_INTEREST_FREE_PERIODS_NOTIFICATION,
                    notification_details={"account_id": str(mock_vault.account_id)},
                )
            ],
        )

        # run function
        result = credit_card._process_payment_due_date(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )
        self.assertEqual(expected_result, result)

        # call assertions
        mock_reverse_uncharged_interest.assert_called_once_with(
            mock_vault,
            live_balances,
            sentinel.denomination,
            {"TXN_TYPE_INTEREST_FREE_PERIOD": None},
            "REVERSE_INTEREST_FREE_PERIOD_INTEREST_UNCHARGED",
        )
        mock_set_accruals_by_sub_type.assert_called_once_with(
            {("", "", ""): {"": Decimal("0")}},  # accruals by sub type
            charge_type=credit_card.PRINCIPAL,
            sub_type=sentinel.sub_type,
            accrual_amount=Decimal("0"),
            ref=sentinel.ref,
        )
        mock_charge_fee.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            live_balances,
            credit_card.LATE_REPAYMENT_FEE,
        )
        mock_get_overdue_balances.assert_called_once_with(live_balances)
        mock_adjust_aggregate_balances.assert_called_once_with(
            mock_vault,
            sentinel.denomination,
            live_balances,
            effective_datetime=DEFAULT_DATETIME,
            credit_limit=sentinel.credit_limit,
        )
        mock_move_outstanding_statement.assert_called_once_with(
            mock_vault,
            live_balances,
            sentinel.denomination,
            Decimal("0"),  # new overdue amount
            supported_txn_types,
            DEFAULT_DATETIME,
        )


@patch.object(credit_card, "_combine_txn_and_type_rates")
class OrderStemsByRepaymentHierarchy(CreditCardTestBase):
    def test_order_stems_by_repayment_hierarchy(self, mock_combine_txn_and_type_rates: MagicMock):
        mock_combine_txn_and_type_rates.return_value = {
            "purchase": "0.01",
            "cash_advance": "0.02",
            "balance_transfer": "0.03",
            "balance_transfer_ref1": "0.02",
            "balance_transfer_ref2": "0.03",
        }

        txn_hierarchy = {"balance_transfer": {"REF1": "0.02", "REF2": "0.03"}}
        txn_type_hierarchy = {
            "purchase": "0.01",
            "cash_advance": "0.02",
            "balance_transfer": "0.03",
        }

        result = credit_card._order_stems_by_repayment_hierarchy(
            txn_stems=["PURCHASE", "CASH_ADVANCE", "BALANCE_TRANSFER"],
            txn_hierarchy=txn_hierarchy,
            txn_type_hierarchy=txn_type_hierarchy,
        )

        expected_result = ["BALANCE_TRANSFER", "CASH_ADVANCE", "PURCHASE"]

        self.assertEqual(result, expected_result)

        mock_combine_txn_and_type_rates.assert_called_with(txn_hierarchy, txn_type_hierarchy)


class CheckTxnTypeTimeLimits(CreditCardTestBase):
    def setUp(self):
        self.mock_vault = self.create_mock()

        self.test_posting_instruction = [
            self.outbound_auth(amount=Decimal("1"), denomination=self.default_denomination)
        ]

        patch_get_parameter = patch.object(credit_card.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()

        patch_get_txn_type_and_ref_from_posting = patch.object(
            credit_card, "_get_txn_type_and_ref_from_posting"
        )
        self.mock_get_txn_type_and_ref_from_posting = (
            patch_get_txn_type_and_ref_from_posting.start()
        )
        self.mock_get_txn_type_and_ref_from_posting.return_value = ("balance_transfer", None)
        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_no_txn_type_time_limits(self):
        common_get_param_return_values = {
            "transaction_type_limits": {
                "cash_advance": {"flat": "250", "percentage": "0.01"},
                "balance_transfer": {},
            },
            "transaction_code_to_type_map": {
                "bb": "balance_transfer",
            },
        }
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=common_get_param_return_values,
        )

        result = credit_card._check_txn_type_time_limits(
            sentinel.mock_vault,
            posting_instructions=self.test_posting_instruction,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertIsNone(result)

    def test_txn_type_not_in_txn_type_with_time_limits(self):
        common_get_param_return_values = {
            "transaction_type_limits": {
                "balance_transfer": {"flat": "250", "percentage": "0.01"},
                "cash_advance": {"allowed_days_after_opening": "14"},
            },
            "transaction_code_to_type_map": {
                "bb": "balance_transfer",
            },
        }
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=common_get_param_return_values,
        )

        result = credit_card._check_txn_type_time_limits(
            self.mock_vault,
            posting_instructions=self.test_posting_instruction,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertIsNone(result)

    def test_on_txn_type_time_limits(self):
        common_get_param_return_values = {
            "transaction_type_limits": {
                "cash_advance": {"flat": "250", "percentage": "0.01"},
                "balance_transfer": {"allowed_days_after_opening": "0"},
            },
            "transaction_code_to_type_map": {
                "bb": "balance_transfer",
            },
        }
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=common_get_param_return_values,
        )

        expected_result = Rejection(
            message="Transaction not permitted outside of configured window "
            "0 days from account opening",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = credit_card._check_txn_type_time_limits(
            self.mock_vault,
            posting_instructions=self.test_posting_instruction,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertEqual(result, expected_result)

    def test_outside_txn_type_time_limits(self):
        common_get_param_return_values = {
            "transaction_type_limits": {
                "cash_advance": {"flat": "250", "percentage": "0.01"},
                "balance_transfer": {"allowed_days_after_opening": "0"},
            },
            "transaction_code_to_type_map": {
                "bb": "balance_transfer",
            },
        }
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters=common_get_param_return_values,
        )

        expected_result = Rejection(
            message="Transaction not permitted outside of configured window "
            "0 days from account opening",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = credit_card._check_txn_type_time_limits(
            self.mock_vault,
            posting_instructions=self.test_posting_instruction,
            effective_datetime=DEFAULT_DATETIME + relativedelta(days=1),
        )

        self.assertEqual(result, expected_result)


class ChargeTxnTypeFeesTest(CreditCardTestBase):
    def setUp(self):
        patch_get_supported_txn_types = patch.object(credit_card, "_get_supported_txn_types")
        self.mock_get_supported_txn_types = patch_get_supported_txn_types.start()
        self.mock_get_supported_txn_types.return_value = ""

        self.common_get_param_return_values = {
            "transaction_code_to_type_map": {
                "xxx": "purchase",
                "aaa": "cash_advance",
                "cc": "transfer",
                "bb": "balance_transfer",
            },
            "transaction_type_fees": {
                "cash_advance": {
                    "over_deposit_only": "False",
                    "percentage_fee": "0.01",
                    "flat_fee": "10",
                },
                "transfer": {
                    "over_deposit_only": "True",
                    "percentage_fee": "0.025",
                    "flat_fee": "80",
                    "combine": "True",
                    "fee_cap": "80",
                },
            },
        }

        self.posting_instructions = self.custom_instruction(DEFAULT_POSTINGS)
        self.latest_balances = BalanceDefaultDict(
            mapping={
                DEFAULT_COORDINATE: SentinelBalance(""),
            }
        )
        self.in_flight_balances = sentinel.in_flight_balances

        patch_get_parameter = patch.object(credit_card.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={**self.common_get_param_return_values},
        )

        patch_get_txn_type_and_ref_from_posting = patch.object(
            credit_card, "_get_txn_type_and_ref_from_posting"
        )
        self.mock_get_txn_type_and_ref_from_posting = (
            patch_get_txn_type_and_ref_from_posting.start()
        )

        patch_get_fee_internal_account = patch.object(credit_card, "_get_fee_internal_account")
        self.mock_get_fee_internal_account = patch_get_fee_internal_account.start()

        patch_rebalance_fees = patch.object(credit_card, "_rebalance_fees")
        self.mock_rebalance_fees = patch_rebalance_fees.start()
        self.mock_rebalance_fees.side_effect = [[SentinelCustomInstruction("transaction_fees")]]
        self.addCleanup(patch.stopall)
        return super().setUp()

    def tests_unsettled_transactions(self):
        result = credit_card._charge_txn_type_fees(
            sentinel.mock_vault,
            posting_instructions=[self.custom_instruction(DEFAULT_POSTINGS)],
            latest_balances=self.latest_balances,
            in_flight_balances=self.in_flight_balances,
            denomination=self.default_denomination,
            effective_datetime=DEFAULT_DATETIME,
        )

        expected_result = []

        self.assertEqual(result, expected_result)

    def tests_settled_transactions_credit_account_committed_balance(self):
        self.mock_get_txn_type_and_ref_from_posting.return_value = ("", None)

        result = credit_card._charge_txn_type_fees(
            sentinel.mock_vault,
            posting_instructions=[
                self.inbound_transfer(amount=Decimal("123"), denomination=self.default_denomination)
            ],
            latest_balances=self.latest_balances,
            in_flight_balances=self.in_flight_balances,
            denomination=self.default_denomination,
            effective_datetime=DEFAULT_DATETIME,
        )

        expected_result = []

        self.assertEqual(result, expected_result)

    def tests_settled_transactions_no_fees(self):
        self.mock_get_txn_type_and_ref_from_posting.return_value = ("", None)

        result = credit_card._charge_txn_type_fees(
            sentinel.mock_vault,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("1"), denomination=self.default_denomination
                )
            ],
            latest_balances=self.latest_balances,
            in_flight_balances=self.in_flight_balances,
            denomination=self.default_denomination,
            effective_datetime=DEFAULT_DATETIME,
        )

        expected_result = []

        self.assertEqual(result, expected_result)

    def tests_settled_transactions_with_fees_no_combine_flat_and_percentage(self):
        self.mock_get_txn_type_and_ref_from_posting.return_value = ("cash_advance", None)
        self.mock_get_fee_internal_account.return_value = sentinel.internal_account

        patch_str_to_bool = patch.object(credit_card.utils, "str_to_bool")
        self.mock_str_to_bool = patch_str_to_bool.start()
        self.mock_str_to_bool.side_effect = [
            False,  # fees.get("combine", "False")
            False,  # fees.get("over_deposit_only", "False")
        ]

        result = credit_card._charge_txn_type_fees(
            sentinel.mock_vault,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("1"), denomination=self.default_denomination
                )
            ],
            latest_balances=self.latest_balances,
            in_flight_balances=self.in_flight_balances,
            denomination=self.default_denomination,
            effective_datetime=DEFAULT_DATETIME,
        )

        expected_result = [SentinelCustomInstruction("transaction_fees")]

        self.assertEqual(result, expected_result)

        self.mock_rebalance_fees.assert_called_once_with(
            sentinel.mock_vault,
            Decimal("10"),
            self.default_denomination,
            self.in_flight_balances,
            self.mock_get_fee_internal_account.return_value,
            "CASH_ADVANCE_FEE",
        )

    def tests_settled_transactions_with_fees_combine_flat_and_percentage(self):
        self.mock_get_txn_type_and_ref_from_posting.return_value = ("cash_advance", None)
        self.mock_get_fee_internal_account.return_value = "TEST"

        patch_str_to_bool = patch.object(credit_card.utils, "str_to_bool")
        self.mock_str_to_bool = patch_str_to_bool.start()
        self.mock_str_to_bool.side_effect = [
            True,  # fees.get("combine", "False")
            True,  # fees.get("over_deposit_only", "False")
        ]

        result = credit_card._charge_txn_type_fees(
            sentinel.mock_vault,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("1"), denomination=self.default_denomination
                )
            ],
            latest_balances=self.latest_balances,
            in_flight_balances=self.in_flight_balances,
            denomination=self.default_denomination,
            effective_datetime=DEFAULT_DATETIME,
        )

        expected_result = [SentinelCustomInstruction("transaction_fees")]

        self.assertEqual(result, expected_result)
        self.mock_rebalance_fees.assert_called_once_with(
            sentinel.mock_vault,
            Decimal("10.01"),  # charges the combined flat fee and percentage
            self.default_denomination,
            self.in_flight_balances,
            self.mock_get_fee_internal_account.return_value,
            "CASH_ADVANCE_FEE",
        )

    def tests_settled_transactions_with_fees_fee_cap_over_0(self):
        self.mock_get_txn_type_and_ref_from_posting.return_value = ("transfer", None)
        self.mock_get_fee_internal_account.return_value = "TEST"

        patch_str_to_bool = patch.object(credit_card.utils, "str_to_bool")
        self.mock_str_to_bool = patch_str_to_bool.start()
        self.mock_str_to_bool.side_effect = [
            True,  # fees.get("combine", "False")
            True,  # fees.get("over_deposit_only", "False")
        ]

        result = credit_card._charge_txn_type_fees(
            sentinel.mock_vault,
            posting_instructions=[
                self.outbound_hard_settlement(
                    amount=Decimal("1"), denomination=self.default_denomination
                )
            ],
            latest_balances=self.latest_balances,
            in_flight_balances=self.in_flight_balances,
            denomination=self.default_denomination,
            effective_datetime=DEFAULT_DATETIME,
        )

        expected_result = [SentinelCustomInstruction("transaction_fees")]

        self.assertEqual(result, expected_result)
        self.mock_rebalance_fees.assert_called_once_with(
            sentinel.mock_vault,
            Decimal("80"),  # charges the combined flat fee and percentage but hits cap
            self.default_denomination,
            self.in_flight_balances,
            self.mock_get_fee_internal_account.return_value,
            "TRANSFER_FEE",
        )


@patch.object(credit_card, "_override_info_balance")
class UpdateInfoBalancesTest(CreditCardTestBase):
    def test_update_info_balances(self, mock_override_info_balance: MagicMock):
        # construct mocks
        mock_vault = sentinel.vault
        mock_override_info_balance.side_effect = [
            [SentinelCustomInstruction("statement_balance")],
            [SentinelCustomInstruction("outstanding_balance")],
            [SentinelCustomInstruction("full_outstanding_balance")],
            [SentinelCustomInstruction("track_statement_repayments")],
            [SentinelCustomInstruction("mad_balance")],
        ]

        # expected result
        expected_result = [
            SentinelCustomInstruction("statement_balance"),
            SentinelCustomInstruction("outstanding_balance"),
            SentinelCustomInstruction("full_outstanding_balance"),
            SentinelCustomInstruction("track_statement_repayments"),
            SentinelCustomInstruction("mad_balance"),
        ]

        # run function
        result = credit_card._update_info_balances(
            mock_vault,
            in_flight_balances=sentinel.in_flight_balances,
            denomination=self.default_denomination,
            statement_amount=Decimal("1"),
            mad=Decimal("2"),
        )

        self.assertListEqual(result, expected_result)
        mock_override_info_balance.assert_has_calls(
            calls=[
                call(
                    mock_vault,
                    sentinel.in_flight_balances,
                    credit_card.STATEMENT_BALANCE,
                    self.default_denomination,
                    Decimal("1"),
                ),
                call(
                    mock_vault,
                    sentinel.in_flight_balances,
                    credit_card.OUTSTANDING_BALANCE,
                    self.default_denomination,
                    Decimal("1"),
                ),
                call(
                    mock_vault,
                    sentinel.in_flight_balances,
                    credit_card.FULL_OUTSTANDING_BALANCE,
                    self.default_denomination,
                    Decimal("1"),
                ),
                call(
                    mock_vault,
                    sentinel.in_flight_balances,
                    credit_card.TRACK_STATEMENT_REPAYMENTS,
                    self.default_denomination,
                    Decimal("0"),
                ),
                call(
                    mock_vault,
                    sentinel.in_flight_balances,
                    credit_card.MAD_BALANCE,
                    self.default_denomination,
                    Decimal("2"),
                ),
            ]
        )


class ValidateTxnTypeAndRefsTest(CreditCardTestBase):
    def setUp(self):
        self.balances = BalanceDefaultDict()
        self.test_posting_instruction = SentinelCustomInstruction("test_posting_instruction")
        self.supported_txn_types = {
            "PURCHASE": [sentinel.txn_ref],
            "CASH_ADVANCE": None,
            "BALANCE_TRANSFER": None,
        }
        self.txn_code_to_type_map = {
            "xxx": "purchase",
            "aaa": "cash_advance",
            "cc": "transfer",
            "bb": "balance_transfer",
        }

        patch_get_txn_type_and_ref_from_posting = patch.object(
            credit_card, "_get_txn_type_and_ref_from_posting"
        )
        self.mock_get_txn_type_and_ref_from_posting = (
            patch_get_txn_type_and_ref_from_posting.start()
        )
        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_inbound_posting_no_validation(self):
        self.mock_get_txn_type_and_ref_from_posting.return_value = ("CASH_ADVANCE", None)

        test_posting_instruction = self.inbound_auth(
            amount=Decimal("1"), denomination=self.default_denomination
        )

        result = credit_card._validate_txn_type_and_refs(
            sentinel.mock_vault,
            balances=self.balances,
            posting_instructions=[
                test_posting_instruction,
            ],
            supported_txn_types=self.supported_txn_types,
            txn_code_to_type_map=self.txn_code_to_type_map,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertIsNone(result)

    def test_supported_txn_type_missing_ref(self):
        self.mock_get_txn_type_and_ref_from_posting.return_value = ("CASH_ADVANCE", None)
        supported_txn_types = {**self.supported_txn_types, "CASH_ADVANCE": [sentinel.txn_ref]}

        expected_rejection = Rejection(
            message="Transaction type CASH_ADVANCE requires a transaction level reference "
            "and none has been specified.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = credit_card._validate_txn_type_and_refs(
            sentinel.mock_vault,
            balances=self.balances,
            posting_instructions=[
                self.test_posting_instruction,
            ],
            supported_txn_types=supported_txn_types,
            txn_code_to_type_map=self.txn_code_to_type_map,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertEqual(result, expected_rejection)

    def test_supported_txn_type_contains_ref(self):
        self.mock_get_txn_type_and_ref_from_posting.return_value = ("CASH_ADVANCE", None)
        supported_txn_types = {**self.supported_txn_types}
        del supported_txn_types["CASH_ADVANCE"]

        result = credit_card._validate_txn_type_and_refs(
            sentinel.mock_vault,
            balances=self.balances,
            posting_instructions=[
                self.test_posting_instruction,
            ],
            supported_txn_types=supported_txn_types,
            txn_code_to_type_map=self.txn_code_to_type_map,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertIsNone(result)

    def test_undefined_params(self):
        self.mock_get_txn_type_and_ref_from_posting.return_value = ("CASH_ADVANCE", "1")

        expected_rejection = Rejection(
            message="1 undefined in parameters for CASH_ADVANCE. " "Please update parameters.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = credit_card._validate_txn_type_and_refs(
            sentinel.mock_vault,
            balances=self.balances,
            posting_instructions=[
                self.test_posting_instruction,
            ],
            supported_txn_types=self.supported_txn_types,
            txn_code_to_type_map=self.txn_code_to_type_map,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertEqual(result, expected_rejection)

    def test_txn_ref_already_in_use(self):
        self.mock_get_txn_type_and_ref_from_posting.return_value = ("CASH_ADVANCE", "REF1")
        supported_txn_types = {**self.supported_txn_types, "CASH_ADVANCE": ["REF1"]}

        expected_rejection = Rejection(
            message="REF1 already in use for CASH_ADVANCE. Please select a unique reference.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        result = credit_card._validate_txn_type_and_refs(
            sentinel.mock_vault,
            balances=BalanceDefaultDict(
                mapping={
                    BalanceCoordinate(
                        account_address="CASH_ADVANCE_REF1_CHARGED",
                        asset=DEFAULT_ASSET,
                        denomination="GBP",
                        phase=Phase.COMMITTED,
                    ): SentinelBalance(""),
                }
            ),
            posting_instructions=[
                self.test_posting_instruction,
            ],
            supported_txn_types=supported_txn_types,
            txn_code_to_type_map=self.txn_code_to_type_map,
            effective_datetime=DEFAULT_DATETIME,
        )

        self.assertEqual(result, expected_rejection)


class SetAccrualsBySubTypeTest(CreditCardTestBase):
    def test_set_accruals_by_sub_type_with_refs(self):
        accruals_by_sub_type = {
            ("PRINCIPAL", "balance_transfer", "PRE_SCOD"): {
                "REF1": Decimal("1"),
                "REF2": Decimal("4"),
            }
        }

        expected_result = {
            ("PRINCIPAL", "balance_transfer", "PRE_SCOD"): {
                "REF1": Decimal("11"),
                "REF2": Decimal("4"),
            },
        }

        credit_card._set_accruals_by_sub_type(
            accruals_by_sub_type=accruals_by_sub_type,
            charge_type="PRINCIPAL",
            sub_type="balance_transfer",
            accrual_amount=Decimal("10"),
            ref="REF1",
            accrual_type="PRE_SCOD",
        )

        self.assertDictEqual(accruals_by_sub_type, expected_result)

    def test_set_accruals_by_sub_type_without_refs(self):
        accruals_by_sub_type = {("PRINCIPAL", "purchase", ""): {"": Decimal("7")}}

        expected_result = {
            ("PRINCIPAL", "purchase", ""): {"": Decimal("17")},
        }

        credit_card._set_accruals_by_sub_type(
            accruals_by_sub_type=accruals_by_sub_type,
            charge_type="PRINCIPAL",
            sub_type="purchase",
            accrual_amount=Decimal("10"),
            ref="",
            accrual_type="",
        )

        self.assertDictEqual(accruals_by_sub_type, expected_result)

    def test_set_accruals_by_sub_type_without_charge_or_sub_types(self):
        accruals_by_sub_type = {("PRINCIPAL", "purchase", "PRE_SCOD"): {"": Decimal("7")}}

        expected_result = {
            ("PRINCIPAL", "purchase", "PRE_SCOD"): {"": Decimal("7")},
            ("", "", ""): {"": Decimal("10.0")},
        }

        credit_card._set_accruals_by_sub_type(
            accruals_by_sub_type=accruals_by_sub_type,
            charge_type="",
            sub_type="",
            accrual_amount=Decimal("10"),
            ref="",
            accrual_type="",
        )

        self.assertDictEqual(accruals_by_sub_type, expected_result)


class CheckTxnTypeCreditLimits(CreditCardTestBase):
    def setUp(self):
        self.balances = BalanceDefaultDict(
            mapping={
                DEFAULT_COORDINATE: SentinelBalance(""),
            }
        )
        self.test_posting_instruction = self.outbound_auth(
            amount=Decimal("1"), denomination=self.default_denomination
        )
        self.txn_code_to_type_map = {
            "xxx": "purchase",
            "aaa": "cash_advance",
            "cc": "transfer",
            "bb": "balance_transfer",
        }

        patch_get_parameter = patch.object(credit_card.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()

        patch_get_txn_type_and_ref_from_posting = patch.object(
            credit_card, "_get_txn_type_and_ref_from_posting"
        )
        self.mock_get_txn_type_and_ref_from_posting = (
            patch_get_txn_type_and_ref_from_posting.start()
        )

        patch_calculate_aggregate_balance = patch.object(
            credit_card, "_calculate_aggregate_balance"
        )
        self.mock_calculate_aggregate_balance = patch_calculate_aggregate_balance.start()

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_no_txn_type_credit_limits(self):
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"transaction_type_limits": {}}
        )

        result = credit_card._check_txn_type_credit_limits(
            sentinel.mock_vault,
            balances=self.balances,
            posting_instructions=[self.test_posting_instruction],
            denomination=self.default_denomination,
            effective_datetime=DEFAULT_DATETIME,
            txn_code_to_type_map=self.txn_code_to_type_map,
        )

        self.assertIsNone(result)

    def test_txn_type_credit_limits_below_limit(self):
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "transaction_type_limits": {
                    "cash_advance": {"flat": "250", "percentage": "0.01"},
                    "balance_transfer": {"allowed_days_after_opening": "14"},
                },
                "credit_limit": Decimal("0"),
                "transaction_references": {"balance_transfer": ["REF1", "REF2"]},
            }
        )

        self.mock_get_txn_type_and_ref_from_posting.return_value = ("balance_transfer", None)

        result = credit_card._check_txn_type_credit_limits(
            sentinel.mock_vault,
            balances=self.balances,
            posting_instructions=[self.test_posting_instruction],
            denomination=self.default_denomination,
            effective_datetime=DEFAULT_DATETIME,
            txn_code_to_type_map=self.txn_code_to_type_map,
        )

        self.assertIsNone(result)

    def test_txn_type_credit_limits_above_limit(self):
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "transaction_type_limits": {
                    "cash_advance": {"flat": "250", "percentage": "0.01"},
                    "balance_transfer": {"allowed_days_after_opening": "14"},
                },
                "credit_limit": Decimal("15"),
                "transaction_references": {"balance_transfer": ["REF1", "REF2"]},
            }
        )

        self.mock_get_txn_type_and_ref_from_posting.return_value = ("cash_advance", None)
        self.mock_calculate_aggregate_balance.return_value = Decimal("7")

        expected_result = Rejection(
            message="Insufficient funds for GBP 1 transaction due to GBP 0.15 limit on transaction "
            "type cash_advance. Outstanding transactions amount to GBP 7",
            reason_code=RejectionReason.INSUFFICIENT_FUNDS,
        )

        result = credit_card._check_txn_type_credit_limits(
            sentinel.mock_vault,
            balances=self.balances,
            posting_instructions=[
                self.outbound_auth(amount=Decimal("1"), denomination=self.default_denomination)
            ],
            denomination=self.default_denomination,
            effective_datetime=DEFAULT_DATETIME,
            txn_code_to_type_map=self.txn_code_to_type_map,
        )

        self.assertEqual(result, expected_result)


class UpdateAuthBucketForOutboundSettlementTest(CreditCardTestBase):
    def setUp(self) -> None:
        self.auth_posting_instruction = self.outbound_auth(
            amount=Decimal("10"),
            denomination=self.default_denomination,
        )
        self.settle_posting_instruction = self.settle_outbound_auth(unsettled_amount=Decimal("10"))

        self.in_flight_balances = sentinel.in_flight_balances

        patch_make_internal_address_transfer = patch.object(
            credit_card, "_make_internal_address_transfer"
        )
        self.mock_make_internal_address_transfer = patch_make_internal_address_transfer.start()
        self.mock_make_internal_address_transfer.return_value = [
            SentinelCustomInstruction("update_auth_instruction")
        ]
        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_no_auth_updates_for_non_outbound_auth_client_transaction(self):
        settlement_posting_instruction = self.outbound_hard_settlement(amount=Decimal("10"))

        client_transaction = ClientTransaction(
            client_transaction_id="test_id",
            account_id=ACCOUNT_ID,
            posting_instructions=[settlement_posting_instruction],
        )

        expected_result = []

        result = credit_card._update_auth_bucket_for_outbound_settlement(
            sentinel.mock_vault,
            client_transaction=client_transaction,
            in_flight_balances=self.in_flight_balances,
            txn_type="CASH_ADVANCE",
            txn_ref="",
        )
        self.assertEqual(result, expected_result)
        self.mock_make_internal_address_transfer.assert_not_called()

    def test_no_auth_updates_for_zero_amount_settlement(self):
        interim_settlement = self.settle_outbound_auth(
            unsettled_amount=Decimal("10"),
            amount=Decimal("10"),
            value_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
        )
        zero_settlement = self.settle_outbound_auth(
            unsettled_amount=Decimal("0"),
            amount=Decimal("0"),
            final=True,
            _from_proto=True,
            value_datetime=DEFAULT_DATETIME + relativedelta(seconds=2),
        )

        client_transaction = ClientTransaction(
            client_transaction_id="test_id",
            account_id=ACCOUNT_ID,
            posting_instructions=[
                self.auth_posting_instruction,
                interim_settlement,
                zero_settlement,
            ],
        )

        expected_result = []
        mock_vault = self.create_mock()
        result = credit_card._update_auth_bucket_for_outbound_settlement(
            mock_vault,
            client_transaction=client_transaction,
            in_flight_balances=self.in_flight_balances,
            txn_type="CASH_ADVANCE",
            txn_ref="",
        )
        self.assertEqual(result, expected_result)
        self.mock_make_internal_address_transfer.assert_not_called()

    def test_auth_bucket_zerod_out_for_final_settlement(self):
        settlement_posting_instruction = self.settle_outbound_auth(
            unsettled_amount=Decimal("10"),
            final=True,
            value_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
        )
        client_transaction = ClientTransaction(
            client_transaction_id="test_id",
            account_id=ACCOUNT_ID,
            tside=credit_card.tside,
            posting_instructions=[self.auth_posting_instruction, settlement_posting_instruction],
        )
        expected_result = [SentinelCustomInstruction("update_auth_instruction")]

        mock_vault = self.create_mock()

        result = credit_card._update_auth_bucket_for_outbound_settlement(
            vault=mock_vault,
            client_transaction=client_transaction,
            in_flight_balances=self.in_flight_balances,
            txn_type="CASH_ADVANCE",
            txn_ref="",
        )

        self.assertListEqual(result, expected_result)
        self.mock_make_internal_address_transfer.assert_called_once_with(
            amount=Decimal("10"),
            denomination=self.default_denomination,
            credit_internal=False,
            custom_address="CASH_ADVANCE_AUTH",
            vault=mock_vault,
            instruction_details={},
            in_flight_balances=sentinel.in_flight_balances,
        )

    def test_auth_bucket_zerod_out_for_final_settlement_with_explicit_amount(self):
        settlement_posting_instruction = self.settle_outbound_auth(
            unsettled_amount=Decimal("10"),
            amount=Decimal("5"),
            final=True,
            value_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
        )
        client_transaction = ClientTransaction(
            client_transaction_id="test_id",
            account_id=ACCOUNT_ID,
            tside=credit_card.tside,
            posting_instructions=[self.auth_posting_instruction, settlement_posting_instruction],
        )
        expected_result = [SentinelCustomInstruction("update_auth_instruction")]

        mock_vault = self.create_mock()

        result = credit_card._update_auth_bucket_for_outbound_settlement(
            vault=mock_vault,
            client_transaction=client_transaction,
            in_flight_balances=self.in_flight_balances,
            txn_type="CASH_ADVANCE",
            txn_ref="",
        )

        self.assertListEqual(result, expected_result)
        self.mock_make_internal_address_transfer.assert_called_once_with(
            amount=Decimal("10"),
            denomination=self.default_denomination,
            credit_internal=False,
            custom_address="CASH_ADVANCE_AUTH",
            vault=mock_vault,
            instruction_details={},
            in_flight_balances=sentinel.in_flight_balances,
        )

    def test_auth_bucket_zerod_out_for_non_final_over_settlement(self):
        settlement_posting_instruction = self.settle_outbound_auth(
            unsettled_amount=Decimal("10"),
            amount=Decimal("12"),
            value_datetime=DEFAULT_DATETIME + relativedelta(seconds=1),
        )
        client_transaction = ClientTransaction(
            client_transaction_id="test_id",
            account_id=ACCOUNT_ID,
            tside=credit_card.tside,
            posting_instructions=[self.auth_posting_instruction, settlement_posting_instruction],
        )
        expected_result = [SentinelCustomInstruction("update_auth_instruction")]

        mock_vault = self.create_mock()

        result = credit_card._update_auth_bucket_for_outbound_settlement(
            vault=mock_vault,
            client_transaction=client_transaction,
            in_flight_balances=self.in_flight_balances,
            txn_type="CASH_ADVANCE",
            txn_ref="",
        )

        self.assertListEqual(result, expected_result)
        self.mock_make_internal_address_transfer.assert_called_once_with(
            amount=Decimal("10"),
            denomination=self.default_denomination,
            credit_internal=False,
            custom_address="CASH_ADVANCE_AUTH",
            vault=mock_vault,
            instruction_details={},
            in_flight_balances=sentinel.in_flight_balances,
        )

    def test_auth_bucket_decreased_for_partial_settlement(self):
        settlement_posting_instruction = self.settle_outbound_auth(
            unsettled_amount=Decimal("10"), amount=Decimal("2")
        )
        client_transaction = ClientTransaction(
            client_transaction_id="test_id",
            account_id=ACCOUNT_ID,
            posting_instructions=[self.auth_posting_instruction, settlement_posting_instruction],
        )

        expected_result = [SentinelCustomInstruction("update_auth_instruction")]
        mock_vault = self.create_mock()
        result = credit_card._update_auth_bucket_for_outbound_settlement(
            vault=mock_vault,
            client_transaction=client_transaction,
            in_flight_balances=self.in_flight_balances,
            txn_type="CASH_ADVANCE",
            txn_ref="",
        )

        self.assertListEqual(result, expected_result)
        self.mock_make_internal_address_transfer.assert_called_once_with(
            amount=Decimal("2"),
            denomination=self.default_denomination,
            credit_internal=False,
            custom_address="CASH_ADVANCE_AUTH",
            vault=mock_vault,
            instruction_details={},
            in_flight_balances=sentinel.in_flight_balances,
        )
