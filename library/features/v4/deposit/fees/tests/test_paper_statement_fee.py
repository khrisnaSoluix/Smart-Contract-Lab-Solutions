# Copyright @ 2023 Thought Machine Group Limited. All rights reserved.
# standard libs
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch, sentinel

# features
import library.features.v4.deposit.fees.paper_statement_fee as paper_statement_fee
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import ScheduleFailover

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    DEFAULT_DENOMINATION,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    SmartContractEventType,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelBalancesObservation,
    SentinelScheduledEvent,
)

PAPER_STATEMENT_FEE_INCOME_ACCOUNT = "PAPER_STATEMENT_FEE_INCOME_ACCOUNT"


class TestPaperStatementFees(FeatureTest):
    def test_paper_statement_fee_event_types(self):
        # run function
        event_types = paper_statement_fee.event_types(product_name="product_a")

        # call assertions
        self.assertListEqual(
            event_types,
            [
                SmartContractEventType(
                    name="APPLY_PAPER_STATEMENT_FEE",
                    scheduler_tag_ids=["PRODUCT_A_APPLY_PAPER_STATEMENT_FEE_AST"],
                )
            ],
        )

    @patch.object(paper_statement_fee.utils, "get_parameter")
    @patch.object(paper_statement_fee.utils, "monthly_scheduled_event")
    def test_paper_statement_fee_scheduled_event(
        self, mock_monthly_scheduled_event: MagicMock, mock_get_parameter: MagicMock
    ):
        # construct mocks
        mock_monthly_scheduled_event.return_value = SentinelScheduledEvent(
            "APPLY_PAPER_STATEMENT_FEE"
        )
        paper_statement_fee_day = "17"
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "paper_statement_fee_day": paper_statement_fee_day,
            }
        )

        # run function
        scheduled_events = paper_statement_fee.scheduled_events(
            vault=sentinel.vault,
            start_datetime=DEFAULT_DATETIME + relativedelta(months=1),
        )

        # call assertions
        self.assertDictEqual(
            scheduled_events,
            {"APPLY_PAPER_STATEMENT_FEE": SentinelScheduledEvent("APPLY_PAPER_STATEMENT_FEE")},
        )

        mock_monthly_scheduled_event.assert_called_once_with(
            vault=sentinel.vault,
            start_datetime=DEFAULT_DATETIME + relativedelta(months=1),
            day=int(paper_statement_fee_day),
            parameter_prefix="paper_statement_fee",
            failover=ScheduleFailover.FIRST_VALID_DAY_AFTER,
        )

    @patch.object(paper_statement_fee.utils, "get_parameter")
    @patch.object(paper_statement_fee.fees, "fee_custom_instruction")
    def test_paper_statement_fee_applied(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "paper_statement_fee_enabled": True,
                "partial_paper_statement_fee_enabled": False,
                "paper_statement_fee_rate": Decimal("3.00"),
                "paper_statement_fee_income_account": (PAPER_STATEMENT_FEE_INCOME_ACCOUNT),
                "denomination": DEFAULT_DENOMINATION,
            }
        )

        mock_fee_custom_instruction.return_value = [sentinel.fee_custom_instruction]
        mock_vault = self.create_mock(account_id=sentinel.account_id)

        # run function
        fee_postings = paper_statement_fee.apply(
            vault=mock_vault, effective_datetime=DEFAULT_DATETIME
        )

        # call assertions
        self.assertListEqual(fee_postings, [sentinel.fee_custom_instruction])

        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name="paper_statement_fee_enabled",
                    is_boolean=True,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name="paper_statement_fee_rate",
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name="paper_statement_fee_income_account",
                    at_datetime=None,
                ),
                call(vault=mock_vault, name="denomination", at_datetime=None),
            ]
        )

    @patch.object(paper_statement_fee.utils, "get_parameter")
    @patch.object(paper_statement_fee.partial_fee, "charge_partial_fee")
    @patch.object(paper_statement_fee.fees, "fee_custom_instruction")
    def test_paper_statement_fee_partially_applied_provided_optional_args(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_charge_partial_fee: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "paper_statement_fee_enabled": True,
                "partial_paper_statement_fee_enabled": True,
                "paper_statement_fee_rate": Decimal("3.00"),
                "paper_statement_fee_income_account": (PAPER_STATEMENT_FEE_INCOME_ACCOUNT),
            }
        )

        mock_fee_custom_instruction.return_value = [sentinel.fee_custom_instruction]
        mock_charge_partial_fee.return_value = [sentinel.partial_fee_instruction]
        mock_vault = self.create_mock()

        # run function
        fee_postings = paper_statement_fee.apply(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=sentinel.denomination,
            balances=sentinel.balances,
            available_balance_feature=sentinel.available_balance,
        )

        # call assertions
        self.assertListEqual(fee_postings, [sentinel.partial_fee_instruction])

        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name=paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_ENABLED,
                    is_boolean=True,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_RATE,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_INCOME_ACCOUNT,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_PARTIAL_FEE_ENABLED,
                    at_datetime=DEFAULT_DATETIME,
                    is_boolean=True,
                    default_value=False,
                    is_optional=True,
                ),
            ]
        )

        mock_charge_partial_fee.assert_called_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            fee_custom_instruction=[sentinel.fee_custom_instruction][0],
            fee_details=paper_statement_fee.PARTIAL_FEE_DETAILS,
            balances=sentinel.balances,
            denomination=sentinel.denomination,
            available_balance_feature=sentinel.available_balance,
        )

    @patch.object(paper_statement_fee.utils, "get_parameter")
    @patch.object(paper_statement_fee.partial_fee, "charge_partial_fee")
    @patch.object(paper_statement_fee.fees, "fee_custom_instruction")
    def test_paper_statement_fee_partially_applied_optional_args_not_provided(
        self,
        mock_fee_custom_instruction: MagicMock,
        mock_charge_partial_fee: MagicMock,
        mock_get_parameter: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "paper_statement_fee_enabled": True,
                "partial_paper_statement_fee_enabled": True,
                "paper_statement_fee_rate": Decimal("3.00"),
                "paper_statement_fee_income_account": (PAPER_STATEMENT_FEE_INCOME_ACCOUNT),
                "denomination": DEFAULT_DENOMINATION,
            }
        )

        mock_fee_custom_instruction.return_value = [sentinel.fee_custom_instruction]
        mock_charge_partial_fee.return_value = [sentinel.partial_fee_instruction]
        mock_vault = self.create_mock(
            balances_observation_fetchers_mapping={
                "EFFECTIVE_FETCHER": SentinelBalancesObservation("live")
            },
        )
        # run function
        fee_postings = paper_statement_fee.apply(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )

        # call assertions
        self.assertListEqual(fee_postings, [sentinel.partial_fee_instruction])

        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=mock_vault,
                    name=paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_ENABLED,
                    is_boolean=True,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_RATE,
                    at_datetime=None,
                ),
                call(
                    vault=mock_vault,
                    name=paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_INCOME_ACCOUNT,
                    at_datetime=None,
                ),
                call(vault=mock_vault, name="denomination", at_datetime=None),
                call(
                    vault=mock_vault,
                    name=paper_statement_fee.PARAM_PAPER_STATEMENT_FEE_PARTIAL_FEE_ENABLED,
                    at_datetime=DEFAULT_DATETIME,
                    is_boolean=True,
                    default_value=False,
                    is_optional=True,
                ),
            ]
        )

        mock_charge_partial_fee.assert_called_with(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
            fee_custom_instruction=[sentinel.fee_custom_instruction][0],
            fee_details=paper_statement_fee.PARTIAL_FEE_DETAILS,
            balances=sentinel.balances_live,
            denomination=DEFAULT_DENOMINATION,
            available_balance_feature=None,
        )

    @patch.object(paper_statement_fee.fees, "fee_custom_instruction")
    @patch.object(paper_statement_fee.utils, "get_parameter")
    def test_paper_statement_fee_not_applied_when_fee_is_zero(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_custom_instruction: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "paper_statement_fee_enabled": True,
                "partial_paper_statement_fee_enabled": False,
                "paper_statement_fee_rate": Decimal("0.00"),
            }
        )

        # run function
        fee_postings = paper_statement_fee.apply(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
        )

        # call assertions
        self.assertListEqual(fee_postings, [])

        mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.vault,
                    name="paper_statement_fee_enabled",
                    is_boolean=True,
                    at_datetime=None,
                ),
                call(
                    vault=sentinel.vault,
                    name="paper_statement_fee_rate",
                    at_datetime=None,
                ),
            ]
        )

        mock_fee_custom_instruction.assert_not_called()

    @patch.object(paper_statement_fee.fees, "fee_custom_instruction")
    @patch.object(paper_statement_fee.utils, "get_parameter")
    def test_paper_statement_fee_not_applied_when_disabled(
        self,
        mock_get_parameter: MagicMock,
        mock_fee_custom_instruction: MagicMock,
    ):
        # construct mocks
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            {
                "paper_statement_fee_enabled": False,
                "paper_statement_fee_rate": Decimal("3.00"),
                "denomination": DEFAULT_DENOMINATION,
            }
        )

        # run functions
        fee_postings = paper_statement_fee.apply(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            denomination=DEFAULT_DENOMINATION,
        )

        # call assertions
        self.assertEqual(fee_postings, [])

        mock_get_parameter.assert_called_once_with(
            vault=sentinel.vault,
            name="paper_statement_fee_enabled",
            is_boolean=True,
            at_datetime=None,
        )

        mock_fee_custom_instruction.assert_not_called()
