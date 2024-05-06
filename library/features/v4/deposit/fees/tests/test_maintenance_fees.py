# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps
from unittest import TestCase
from unittest.mock import MagicMock, call, patch, sentinel

# features
import library.features.v4.deposit.fees.maintenance_fees as maintenance_fees
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    ACCOUNT_ID,
    DEFAULT_DATETIME,
    DEFAULT_DENOMINATION,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ScheduledEvent,
    SmartContractEventType,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelCustomInstruction,
    SentinelScheduledEvent,
    SentinelScheduleExpression,
)

MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT = "MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT"
ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT = "ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT"


def generate_mock_waive_fee_condition(waive_fee: bool):
    waive_fee_condition = MagicMock(maintenance_fees.deposit_interfaces.WaiveFeeCondition)

    def waive_fees(*args, **kwargs):
        return waive_fee

    waive_fee_condition.waive_fees.side_effect = waive_fees

    return waive_fee_condition


class TestMonthlyMaintenanceFees(FeatureTest):
    def test_monthly_maintenance_fee_event_types(self):
        event_types = maintenance_fees.event_types(
            product_name="product_a", frequency=maintenance_fees.MONTHLY
        )
        self.assertListEqual(
            event_types,
            [
                SmartContractEventType(
                    name=maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
                    scheduler_tag_ids=[f"PRODUCT_A_{maintenance_fees.APPLY_MONTHLY_FEE_EVENT}_AST"],
                )
            ],
        )

    def test_maintenance_fee_event_types_not_applied_for_unrecognised_frequency(self):
        event_types = maintenance_fees.event_types(product_name="product_a", frequency="daily")
        self.assertListEqual(
            event_types,
            [],
        )

    @patch.object(maintenance_fees.utils, "get_parameter")
    def test_scheduled_event_invalid_frequency(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "maintenance_fee_application_day": "17",
            }
        )
        scheduled_events = maintenance_fees.scheduled_events(
            vault=sentinel.vault, start_datetime=DEFAULT_DATETIME, frequency="QUARTERLY"
        )

        self.assertEquals(scheduled_events, {})

    @patch.object(maintenance_fees.utils, "get_parameter")
    @patch.object(maintenance_fees.utils, "monthly_scheduled_event")
    def test_monthly_maintenance_fee_scheduled_event(
        self, mock_monthly_scheduled_event: MagicMock, mock_get_parameter: MagicMock
    ):
        mock_monthly_scheduled_event.return_value = SentinelScheduledEvent(
            maintenance_fees.APPLY_MONTHLY_FEE_EVENT
        )

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "maintenance_fee_application_day": "17",
            }
        )

        scheduled_events = maintenance_fees.scheduled_events(
            vault=sentinel.vault,
            start_datetime=DEFAULT_DATETIME,
            frequency=maintenance_fees.MONTHLY,
        )

        self.assertDictEqual(
            scheduled_events,
            {
                maintenance_fees.APPLY_MONTHLY_FEE_EVENT: SentinelScheduledEvent(
                    maintenance_fees.APPLY_MONTHLY_FEE_EVENT
                )
            },
        )

        mock_monthly_scheduled_event.assert_called_once_with(
            vault=sentinel.vault,
            start_datetime=DEFAULT_DATETIME + relativedelta(months=1),
            parameter_prefix="maintenance_fee_application",
            day=17,
        )

    @patch.object(
        maintenance_fees.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    @patch.object(maintenance_fees.utils, "get_parameter")
    @patch.object(maintenance_fees.fees, "fee_custom_instruction")
    def test_monthly_maintenance_fee_applied(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "account_tier_names": dumps(["Z"]),
                "denomination": DEFAULT_DENOMINATION,
                "monthly_maintenance_fee_income_account": MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
                "monthly_maintenance_fee_by_tier": dumps(
                    {
                        "UPPER_TIER": "0",
                        "MIDDLE_TIER": "0",
                        "LOWER_TIER": "10",
                    }
                ),
                "partial_maintenance_fee_enabled": False,
            }
        )
        mock_get_tiered_parameter_value_based_on_account_tier.return_value = Decimal("10")

        mock_fee_custom_instruction.return_value = [sentinel.fee_custom_instruction]
        mock_vault = self.create_mock()
        fee_postings = maintenance_fees.apply_monthly_fee(
            vault=mock_vault, effective_datetime=sentinel.datetime
        )

        self.assertListEqual(fee_postings, [sentinel.fee_custom_instruction])
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=ACCOUNT_ID,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal("10"),
            internal_account=MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_FEE",
            },
        )

    @patch.object(
        maintenance_fees.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    @patch.object(maintenance_fees.utils, "get_parameter")
    @patch.object(maintenance_fees.partial_fee, "charge_partial_fee")
    @patch.object(maintenance_fees.fees, "fee_custom_instruction")
    def test_monthly_maintenance_fee_partially_applied_default_args_provided(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_partial_fee: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "account_tier_names": dumps(["LOWER_TIER"]),
                "monthly_maintenance_fee_income_account": MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
                "monthly_maintenance_fee_by_tier": dumps(
                    {
                        "UPPER_TIER": "0",
                        "MIDDLE_TIER": "0",
                        "LOWER_TIER": "10",
                    }
                ),
                "partial_maintenance_fee_enabled": True,
            }
        )
        mock_get_tiered_parameter_value_based_on_account_tier.return_value = Decimal("10")
        mock_partial_fee.return_value = [sentinel.updated_fee_custom_instruction]
        mock_fee_custom_instruction.return_value = [sentinel.fee_custom_instruction]
        mock_vault = self.create_mock()

        fee_postings = maintenance_fees.apply_monthly_fee(
            vault=mock_vault,
            effective_datetime=sentinel.datetime,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
            available_balance_feature=sentinel.available_balance,
        )

        self.assertListEqual(fee_postings, [sentinel.updated_fee_custom_instruction])

        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name="monthly_maintenance_fee_income_account",
                    at_datetime=sentinel.datetime,
                ),
                call(
                    vault=mock_vault,
                    name="monthly_maintenance_fee_by_tier",
                    at_datetime=sentinel.datetime,
                    is_json=True,
                ),
                call(mock_vault, "account_tier_names", is_json=True),
                call(
                    vault=mock_vault,
                    name="partial_maintenance_fee_enabled",
                    at_datetime=sentinel.datetime,
                    is_boolean=True,
                    is_optional=True,
                    default_value=False,
                ),
            ]
        )

        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=ACCOUNT_ID,
            denomination=sentinel.denomination,
            amount=Decimal("10"),
            internal_account=MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
            },
        )
        mock_partial_fee.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=sentinel.datetime,
            fee_custom_instruction=sentinel.fee_custom_instruction,
            fee_details=maintenance_fees.PARTIAL_FEE_DETAILS,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            available_balance_feature=sentinel.available_balance,
        )

    @patch.object(
        maintenance_fees.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    @patch.object(maintenance_fees.utils, "get_parameter")
    @patch.object(maintenance_fees.partial_fee, "charge_partial_fee")
    @patch.object(maintenance_fees.fees, "fee_custom_instruction")
    def test_monthly_maintenance_fee_partially_applied_default_args_not_provided(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_partial_fee: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "account_tier_names": dumps(["LOWER_TIER"]),
                "monthly_maintenance_fee_income_account": MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
                "monthly_maintenance_fee_by_tier": dumps(
                    {
                        "UPPER_TIER": "0",
                        "MIDDLE_TIER": "0",
                        "LOWER_TIER": "10",
                    }
                ),
                "partial_maintenance_fee_enabled": True,
                "denomination": "GBP",
            }
        )
        mock_get_tiered_parameter_value_based_on_account_tier.return_value = Decimal("10")
        mock_partial_fee.return_value = [sentinel.updated_fee_custom_instruction]
        mock_fee_custom_instruction.return_value = [sentinel.fee_custom_instruction]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                maintenance_fees.fetchers.EFFECTIVE_OBSERVATION_FETCHER_ID: SentinelBalancesObservation(  # noqa: E501
                    "effective"
                )
            }
        )

        fee_postings = maintenance_fees.apply_monthly_fee(
            vault=mock_vault,
            effective_datetime=sentinel.datetime,
            available_balance_feature=sentinel.available_balance,
        )

        self.assertListEqual(fee_postings, [sentinel.updated_fee_custom_instruction])

        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name="monthly_maintenance_fee_income_account",
                    at_datetime=sentinel.datetime,
                ),
                call(
                    vault=mock_vault,
                    name="monthly_maintenance_fee_by_tier",
                    at_datetime=sentinel.datetime,
                    is_json=True,
                ),
                call(mock_vault, "account_tier_names", is_json=True),
                call(vault=mock_vault, name="denomination", at_datetime=sentinel.datetime),
                call(
                    vault=mock_vault,
                    name="partial_maintenance_fee_enabled",
                    at_datetime=sentinel.datetime,
                    is_boolean=True,
                    is_optional=True,
                    default_value=False,
                ),
            ]
        )

        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=ACCOUNT_ID,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal("10"),
            internal_account=MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_FEE",
            },
        )
        mock_partial_fee.assert_called_once_with(
            vault=mock_vault,
            effective_datetime=sentinel.datetime,
            fee_custom_instruction=sentinel.fee_custom_instruction,
            fee_details=maintenance_fees.PARTIAL_FEE_DETAILS,
            balances=sentinel.balances_effective,
            denomination="GBP",
            available_balance_feature=sentinel.available_balance,
        )

    @patch.object(maintenance_fees.utils, "get_parameter")
    @patch.object(maintenance_fees.account_tiers, "get_account_tier")
    @patch.object(
        maintenance_fees.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    @patch.object(maintenance_fees.fees, "fee_custom_instruction")
    def test_monthly_maintenance_fee_not_applied(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_tiered_parameter_value_based_on_account_tier.return_value = Decimal("0")
        mock_get_account_tier.return_value = "LOWER_TIER"
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": DEFAULT_DENOMINATION,
                "monthly_maintenance_fee_income_account": MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
                "monthly_maintenance_fee_by_tier": dumps(
                    {
                        "UPPER_TIER": "0",
                        "MIDDLE_TIER": "0",
                        "LOWER_TIER": "0",
                    }
                ),
                "partial_maintenance_fee_enabled": False,
            }
        )
        mock_vault = self.create_mock()

        mock_fee_custom_instruction.return_value = []
        fee_postings = maintenance_fees.apply_monthly_fee(
            vault=mock_vault, effective_datetime=sentinel.datetime
        )

        self.assertEqual(fee_postings, [])

        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name="monthly_maintenance_fee_income_account",
                    at_datetime=sentinel.datetime,
                ),
                call(
                    vault=mock_vault,
                    name="monthly_maintenance_fee_by_tier",
                    at_datetime=sentinel.datetime,
                    is_json=True,
                ),
                call(vault=mock_vault, name="denomination", at_datetime=sentinel.datetime),
                call(
                    vault=mock_vault,
                    name="partial_maintenance_fee_enabled",
                    at_datetime=sentinel.datetime,
                    is_boolean=True,
                    is_optional=True,
                    default_value=False,
                ),
            ],
        )

        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=ACCOUNT_ID,
            denomination="GBP",
            amount=Decimal("0"),
            internal_account=MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_FEE",
            },
        )

    @patch.object(maintenance_fees.utils, "get_parameter")
    @patch.object(maintenance_fees.account_tiers, "get_account_tier")
    @patch.object(
        maintenance_fees.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    @patch.object(maintenance_fees.fees, "fee_custom_instruction")
    def test_monthly_maintenance_fee_value_not_defined_for_tier(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_tiered_parameter_value_based_on_account_tier.return_value = None
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "account_tier_names": dumps(["UPPER_TIER , LOWER_TIER"]),
                "denomination": DEFAULT_DENOMINATION,
                "monthly_maintenance_fee_income_account": MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
                "monthly_maintenance_fee_by_tier": dumps(
                    {
                        "UPPER_TIER": "0",
                        "LOWER_TIER": "0",
                    }
                ),
                "partial_maintenance_fee_enabled": False,
            }
        )
        mock_vault = self.create_mock()
        mock_fee_custom_instruction.return_value = []
        fee_postings = maintenance_fees.apply_monthly_fee(
            vault=mock_vault, effective_datetime=sentinel.datetime
        )

        self.assertEqual(fee_postings, [])

        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name="monthly_maintenance_fee_income_account",
                    at_datetime=sentinel.datetime,
                ),
                call(
                    vault=mock_vault,
                    name="monthly_maintenance_fee_by_tier",
                    at_datetime=sentinel.datetime,
                    is_json=True,
                ),
                call(
                    vault=mock_vault,
                    name="denomination",
                    at_datetime=sentinel.datetime,
                ),
                call(
                    vault=mock_vault,
                    name="partial_maintenance_fee_enabled",
                    at_datetime=sentinel.datetime,
                    is_boolean=True,
                    is_optional=True,
                    default_value=False,
                ),
            ],
        )

        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=ACCOUNT_ID,
            denomination="GBP",
            amount=Decimal("0"),
            internal_account=MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": "APPLY_MONTHLY_FEE",
            },
        )

    def test_monthly_maintenance_fee_waived(self):
        # construct mocks
        mock_vault = self.create_mock()

        mock_fee_waive_condition = generate_mock_waive_fee_condition(waive_fee=True)
        mock_fee_waive_condition_false = generate_mock_waive_fee_condition(waive_fee=False)

        # run function
        result = maintenance_fees.apply_monthly_fee(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            monthly_fee_waive_conditions=[mock_fee_waive_condition, mock_fee_waive_condition_false],
        )

        # assertions
        self.assertEqual([], result)

    @patch.object(maintenance_fees.fees, "fee_custom_instruction")
    @patch.object(maintenance_fees.account_tiers, "get_account_tier")
    @patch.object(maintenance_fees.utils, "get_parameter")
    def test_monthly_maintenance_fee_not_waived(
        self,
        mock_get_parameter: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_fee_custom_instruction: MagicMock,
    ):
        # construct mocks
        mock_vault = self.create_mock()
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "maintenance_fee_application_day": "17",
                "monthly_maintenance_fee_income_account": MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
                "monthly_maintenance_fee_by_tier": {"LOWER_TIER": "5"},
                "account_tier_names": ["LOWER_TIER"],
                "denomination": DEFAULT_DENOMINATION,
                "partial_maintenance_fee_enabled": False,
            }
        )
        mock_get_account_tier.return_value = "LOWER_TIER"
        mock_fee_custom_instruction.return_value = [SentinelCustomInstruction("fee_instruction")]
        mock_fee_waive_condition_1 = generate_mock_waive_fee_condition(waive_fee=False)
        mock_fee_waive_condition_2 = generate_mock_waive_fee_condition(waive_fee=False)

        # expected result
        expected_result = [SentinelCustomInstruction("fee_instruction")]

        # run function
        result = maintenance_fees.apply_monthly_fee(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            monthly_fee_waive_conditions=[mock_fee_waive_condition_1, mock_fee_waive_condition_2],
        )

        # assertions
        self.assertEqual(expected_result, result)
        mock_get_account_tier.assert_called_once_with(mock_vault)
        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=mock_vault.account_id,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal("5"),
            internal_account=MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
            instruction_details={
                "description": "Monthly maintenance fee",
                "event": maintenance_fees.APPLY_MONTHLY_FEE_EVENT,
            },
        )


class TestAnnualMaintenanceFees(FeatureTest):
    def test_annual_maintenance_fee_event_types(self):
        event_types = maintenance_fees.event_types(product_name="product_a", frequency="annually")
        self.assertListEqual(
            event_types,
            [
                SmartContractEventType(
                    name=maintenance_fees.APPLY_ANNUAL_FEE_EVENT,
                    scheduler_tag_ids=[f"PRODUCT_A_{maintenance_fees.APPLY_ANNUAL_FEE_EVENT}_AST"],
                )
            ],
        )

    def test_maintenance_fee_event_types_not_applied(self):
        event_types = maintenance_fees.event_types(product_name="product_a", frequency="daily")
        self.assertListEqual(
            event_types,
            [],
        )

    @patch.object(maintenance_fees.utils, "get_parameter")
    @patch.object(maintenance_fees.utils, "get_schedule_expression_from_parameters")
    @patch.object(maintenance_fees.utils, "get_next_schedule_date")
    def test_annual_maintenance_fee_scheduled_event(
        self,
        mock_get_next_schedule_date: MagicMock,
        mock_get_schedule_expression_from_parameters: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        mock_get_next_schedule_date.return_value = DEFAULT_DATETIME
        mock_get_schedule_expression_from_parameters.return_value = SentinelScheduleExpression(
            "get_schedule_expression_from_parameters"
        )
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "maintenance_fee_application_day": "17",
            }
        )

        scheduled_events = maintenance_fees.scheduled_events(
            vault=sentinel, start_datetime=DEFAULT_DATETIME, frequency=maintenance_fees.ANNUALLY
        )

        self.assertDictEqual(
            scheduled_events,
            {
                maintenance_fees.APPLY_ANNUAL_FEE_EVENT: ScheduledEvent(
                    start_datetime=DEFAULT_DATETIME + relativedelta(years=1),
                    expression=SentinelScheduleExpression(
                        "get_schedule_expression_from_parameters"
                    ),
                )
            },
        )
        mock_get_next_schedule_date.assert_called_once_with(
            start_date=DEFAULT_DATETIME,
            schedule_frequency=maintenance_fees.ANNUALLY,
            intended_day=17,
        )
        mock_get_schedule_expression_from_parameters.assert_called_once_with(
            vault=sentinel,
            parameter_prefix=maintenance_fees.MAINTENANCE_FEE_APPLICATION_PREFIX,
            day=1,
            month=DEFAULT_DATETIME.month,
            year=None,
        )

    @patch.object(
        maintenance_fees.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    @patch.object(maintenance_fees.account_tiers, "get_account_tier")
    @patch.object(maintenance_fees.utils, "get_parameter")
    @patch.object(maintenance_fees.fees, "fee_custom_instruction")
    def test_annual_maintenance_fee_applied(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
    ):
        annual_maintenance_fee_tiers = sentinel.annual_maintenance_fee_tiers
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": DEFAULT_DENOMINATION,
                "annual_maintenance_fee_by_tier": annual_maintenance_fee_tiers,
                "annual_maintenance_fee_income_account": ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
            }
        )
        mock_get_account_tier.return_value = sentinel.lower_tier
        mock_get_tiered_parameter_value_based_on_account_tier.return_value = 5

        mock_vault = self.create_mock()

        mock_fee_custom_instruction.return_value = [sentinel.fee_custom_instruction]
        fee_postings = maintenance_fees.apply_annual_fee(
            vault=mock_vault, effective_datetime=sentinel.datetime
        )

        self.assertListEqual(fee_postings, [sentinel.fee_custom_instruction])
        mock_get_tiered_parameter_value_based_on_account_tier.assert_called_once_with(
            tiered_parameter=annual_maintenance_fee_tiers,
            tier=sentinel.lower_tier,
            convert=Decimal,
        )
        mock_get_account_tier.assert_called_once_with(mock_vault)

        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=ACCOUNT_ID,
            denomination=DEFAULT_DENOMINATION,
            amount=Decimal("5"),
            internal_account=ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
            instruction_details={
                "description": "Annual maintenance fee",
                "event": "APPLY_ANNUAL_FEE",
            },
        )

    @patch.object(
        maintenance_fees.account_tiers, "get_tiered_parameter_value_based_on_account_tier"
    )
    @patch.object(maintenance_fees.account_tiers, "get_account_tier")
    @patch.object(maintenance_fees.utils, "get_parameter")
    @patch.object(maintenance_fees.fees, "fee_custom_instruction")
    def test_annual_maintenance_fee_not_applied(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
        mock_get_account_tier: MagicMock,
        mock_get_tiered_parameter_value_based_on_account_tier: MagicMock,
    ):
        annual_maintenance_fee_tiers = sentinel.annual_maintenance_fee_tiers
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "denomination": DEFAULT_DENOMINATION,
                "annual_maintenance_fee_by_tier": annual_maintenance_fee_tiers,
                "annual_maintenance_fee_income_account": ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
            }
        )

        mock_get_account_tier.return_value = sentinel.lower_tier
        mock_get_tiered_parameter_value_based_on_account_tier.return_value = 0

        mock_fee_custom_instruction.return_value = []
        mock_vault = self.create_mock()
        fee_postings = maintenance_fees.apply_annual_fee(
            vault=mock_vault, effective_datetime=sentinel.datetime
        )

        self.assertEqual(fee_postings, [])

        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name="annual_maintenance_fee_income_account",
                    at_datetime=sentinel.datetime,
                ),
                call(
                    vault=mock_vault,
                    name="annual_maintenance_fee_by_tier",
                    at_datetime=sentinel.datetime,
                    is_json=True,
                ),
                call(vault=mock_vault, name="denomination", at_datetime=sentinel.datetime),
            ],
        )
        mock_get_tiered_parameter_value_based_on_account_tier.assert_called_once_with(
            tiered_parameter=annual_maintenance_fee_tiers,
            tier=sentinel.lower_tier,
            convert=Decimal,
        )
        mock_get_account_tier.assert_called_once_with(mock_vault)

        mock_fee_custom_instruction.assert_called_once_with(
            customer_account_id=ACCOUNT_ID,
            denomination="GBP",
            amount=Decimal("0"),
            internal_account=ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
            instruction_details={
                "description": "Annual maintenance fee",
                "event": "APPLY_ANNUAL_FEE",
            },
        )


class TestPrivateHelpers(TestCase):
    @patch.object(maintenance_fees.utils, "get_parameter")
    def test_get_monthly_internal_income_account(self, mock_get_param: MagicMock):
        mock_get_param.return_value = sentinel.income_account

        resp = maintenance_fees._get_monthly_internal_income_account(
            vault=sentinel.vault, effective_datetime=sentinel.datetime
        )

        self.assertEqual(resp, sentinel.income_account)
        mock_get_param.assert_called_once_with(
            vault=sentinel.vault,
            name=maintenance_fees.PARAM_MONTHLY_MAINTENANCE_FEE_INCOME_ACCOUNT,
            at_datetime=sentinel.datetime,
        )
