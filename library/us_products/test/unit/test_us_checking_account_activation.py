# standard libs
from dateutil.relativedelta import relativedelta
from unittest.mock import MagicMock, patch, sentinel

# library
from library.us_products.contracts.template import us_checking_account
from library.us_products.test.unit.test_us_checking_account_common import CheckingAccountTest

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import DEFAULT_DATETIME
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    ActivationHookArguments,
    ActivationHookResult,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelScheduledEvent,
)


class ActivationHookTest(CheckingAccountTest):
    @patch.object(us_checking_account.maintenance_fees, "scheduled_events")
    @patch.object(us_checking_account.paper_statement_fee, "scheduled_events")
    @patch.object(us_checking_account.minimum_monthly_balance, "scheduled_events")
    @patch.object(us_checking_account.inactivity_fee, "scheduled_events")
    @patch.object(us_checking_account.interest_application, "scheduled_events")
    @patch.object(us_checking_account.tiered_interest_accrual, "scheduled_events")
    def test_activation_returns_scheduled_events(
        self,
        mock_interest_tiered_accrual_scheduled_events: MagicMock,
        mock_interest_application_scheduled_events: MagicMock,
        mock_inactivity_fee_scheduled_events: MagicMock,
        mock_minimum_monthly_balance_scheduled_events: MagicMock,
        mock_paper_statement_fee_schedule_events: MagicMock,
        mock_maintenance_fees_scheduled_events: MagicMock,
    ):
        # construct values
        accrual_schedule = SentinelScheduledEvent("accrual_schedule")
        application_schedule = SentinelScheduledEvent("application_schedule")
        inactivity_fee_schedule = SentinelScheduledEvent("inactivity_fee_schedule")
        min_monthly_balance_schedule = SentinelScheduledEvent("min_monthly_balance")
        paper_statement_fee_schedule = SentinelScheduledEvent("paper_statement_fee_schedule")
        monthly_maintenance_fee_schedule = SentinelScheduledEvent("monthly_maintenance_fee")

        # construct mocks
        mock_interest_tiered_accrual_scheduled_events.return_value = {
            us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT: accrual_schedule,
        }
        mock_interest_application_scheduled_events.return_value = {
            us_checking_account.interest_application.APPLICATION_EVENT: application_schedule,
        }
        mock_inactivity_fee_scheduled_events.return_value = {
            us_checking_account.inactivity_fee.APPLICATION_EVENT: inactivity_fee_schedule,
        }
        mock_minimum_monthly_balance_scheduled_events.return_value = {
            us_checking_account.minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT: (
                min_monthly_balance_schedule
            ),
        }
        mock_paper_statement_fee_schedule_events.return_value = {
            us_checking_account.paper_statement_fee.APPLICATION_EVENT: paper_statement_fee_schedule,
        }
        mock_maintenance_fees_scheduled_events.return_value = {
            us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT: (
                monthly_maintenance_fee_schedule
            ),
        }

        # expected result
        expected_result = ActivationHookResult(
            scheduled_events_return_value={
                us_checking_account.tiered_interest_accrual.ACCRUAL_EVENT: accrual_schedule,
                us_checking_account.interest_application.APPLICATION_EVENT: application_schedule,
                us_checking_account.inactivity_fee.APPLICATION_EVENT: inactivity_fee_schedule,
                us_checking_account.minimum_monthly_balance.APPLY_MINIMUM_MONTHLY_BALANCE_EVENT: (
                    min_monthly_balance_schedule
                ),
                us_checking_account.paper_statement_fee.APPLICATION_EVENT: (
                    paper_statement_fee_schedule
                ),
                us_checking_account.maintenance_fees.APPLY_MONTHLY_FEE_EVENT: (
                    monthly_maintenance_fee_schedule
                ),
            }
        )

        # run hook
        result = us_checking_account.activation_hook(
            sentinel.vault, ActivationHookArguments(effective_datetime=DEFAULT_DATETIME)
        )
        self.assertEqual(result, expected_result)

        # call assertions
        mock_interest_tiered_accrual_scheduled_events.assert_called_once_with(
            vault=sentinel.vault,
            start_datetime=DEFAULT_DATETIME.replace(hour=0, minute=0, second=0, microsecond=0)
            + relativedelta(days=1),
        )
        mock_interest_application_scheduled_events.assert_called_once_with(
            vault=sentinel.vault,
            reference_datetime=DEFAULT_DATETIME,
        )
        mock_inactivity_fee_scheduled_events.assert_called_once_with(
            vault=sentinel.vault,
            start_datetime=DEFAULT_DATETIME + relativedelta(months=1),
        )
        mock_minimum_monthly_balance_scheduled_events.assert_called_once_with(
            vault=sentinel.vault,
            start_datetime=DEFAULT_DATETIME + relativedelta(months=1),
        )
        mock_maintenance_fees_scheduled_events.assert_called_once_with(
            vault=sentinel.vault,
            start_datetime=DEFAULT_DATETIME,
            frequency=us_checking_account.maintenance_fees.MONTHLY,
        )
        mock_paper_statement_fee_schedule_events.assert_called_once_with(
            vault=sentinel.vault,
            start_datetime=DEFAULT_DATETIME + relativedelta(months=1),
        )
