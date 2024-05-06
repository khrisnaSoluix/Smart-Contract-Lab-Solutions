# standard libs
from unittest.mock import MagicMock, call, patch, sentinel

# features
import library.features.v4.lending.repayment_holiday as repayment_holiday
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    RejectionReason,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.supervisor.common import (
    SupervisorFeatureTest,
)


class BlockingFlagTests(FeatureTest):
    def setUp(self):
        # re-use mock across tests and retain ability to inspect calls if required
        is_flag_in_list_applied_patcher = patch.object(
            repayment_holiday.utils,
            "is_flag_in_list_applied",
            MagicMock(return_value=sentinel.boolean),
        )
        self.addCleanup(is_flag_in_list_applied_patcher.stop)
        self.mock_is_flag_in_list_applied = is_flag_in_list_applied_patcher.start()

    def test_is_interest_accrual_blocked(self):
        self.assertEqual(
            repayment_holiday.is_interest_accrual_blocked(
                vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
            ),
            sentinel.boolean,
        )
        self.mock_is_flag_in_list_applied.assert_called_once_with(
            vault=sentinel.vault,
            parameter_name="interest_accrual_blocking_flags",
            effective_datetime=sentinel.effective_datetime,
        )

    def test_are_notifications_blocked(self):
        self.assertEqual(
            repayment_holiday.are_notifications_blocked(
                vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
            ),
            sentinel.boolean,
        )
        self.mock_is_flag_in_list_applied.assert_called_once_with(
            vault=sentinel.vault,
            parameter_name="notification_blocking_flags",
            effective_datetime=sentinel.effective_datetime,
        )

    def test_is_delinquency_blocked(self):
        self.assertEqual(
            repayment_holiday.is_delinquency_blocked(
                vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
            ),
            sentinel.boolean,
        )
        self.mock_is_flag_in_list_applied.assert_called_once_with(
            vault=sentinel.vault,
            parameter_name="delinquency_blocking_flags",
            effective_datetime=sentinel.effective_datetime,
        )

    def test_is_due_amount_calculation_blocked(self):
        self.assertEqual(
            repayment_holiday.is_due_amount_calculation_blocked(
                vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
            ),
            sentinel.boolean,
        )
        self.mock_is_flag_in_list_applied.assert_called_once_with(
            vault=sentinel.vault,
            parameter_name="due_amount_calculation_blocking_flags",
            effective_datetime=sentinel.effective_datetime,
        )

    def test_is_overdue_amount_calculation_blocked(self):
        self.assertEqual(
            repayment_holiday.is_overdue_amount_calculation_blocked(
                vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
            ),
            sentinel.boolean,
        )
        self.mock_is_flag_in_list_applied.assert_called_once_with(
            vault=sentinel.vault,
            parameter_name="overdue_amount_calculation_blocking_flags",
            effective_datetime=sentinel.effective_datetime,
        )

    def test_is_penalty_accrual_blocked(self):
        self.assertEqual(
            repayment_holiday.is_penalty_accrual_blocked(
                vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
            ),
            sentinel.boolean,
        )
        self.mock_is_flag_in_list_applied.assert_called_once_with(
            vault=sentinel.vault,
            parameter_name="penalty_blocking_flags",
            effective_datetime=sentinel.effective_datetime,
        )

    def test_is_repayment_blocked(self):
        self.assertEqual(
            repayment_holiday.is_repayment_blocked(
                vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
            ),
            sentinel.boolean,
        )
        self.mock_is_flag_in_list_applied.assert_called_once_with(
            vault=sentinel.vault,
            parameter_name="repayment_blocking_flags",
            effective_datetime=sentinel.effective_datetime,
        )


@patch.object(repayment_holiday, "is_repayment_blocked")
class ValidateRepaymentTest(FeatureTest):
    def test_reject_repayment_returns_none(self, mock_is_repayment_blocked: MagicMock):
        mock_is_repayment_blocked.return_value = False
        self.assertIsNone(
            repayment_holiday.reject_repayment(
                vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
            )
        )
        mock_is_repayment_blocked.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
        )

    def test_reject_repayment_returns_rejection(self, mock_is_repayment_blocked: MagicMock):
        mock_is_repayment_blocked.return_value = True
        expected_result = Rejection(
            message="Repayments are blocked for this account.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        self.assertEqual(
            repayment_holiday.reject_repayment(
                vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
            ),
            expected_result,
        )
        mock_is_repayment_blocked.assert_called_once_with(
            vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
        )


@patch.object(repayment_holiday, "is_due_amount_calculation_blocked")
class AmortisationTest(FeatureTest):
    def test_no_preference_no_flag_at_period_start(
        self, mock_is_due_amount_calculation_blocked: MagicMock
    ):
        mock_is_due_amount_calculation_blocked.return_value = False

        self.assertFalse(
            repayment_holiday.should_trigger_reamortisation_no_impact_preference(
                vault=sentinel.vault,
                period_start_datetime=sentinel.period_start_datetime,
                period_end_datetime=sentinel.period_end_datetime,
            )
        )
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.period_start_datetime,
        )

    def test_no_preference_flag_at_period_start_not_at_end(
        self, mock_is_due_amount_calculation_blocked: MagicMock
    ):
        mock_is_due_amount_calculation_blocked.side_effect = [True, False]

        self.assertTrue(
            repayment_holiday.should_trigger_reamortisation_no_impact_preference(
                vault=sentinel.vault,
                period_start_datetime=sentinel.period_start_datetime,
                period_end_datetime=sentinel.period_end_datetime,
            )
        )
        mock_is_due_amount_calculation_blocked.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.vault,
                    effective_datetime=sentinel.period_start_datetime,
                ),
                call(
                    vault=sentinel.vault,
                    effective_datetime=sentinel.period_end_datetime,
                ),
            ]
        )
        self.assertEqual(mock_is_due_amount_calculation_blocked.call_count, 2)

    def test_no_preference_flag_at_period_start_and_end(
        self, mock_is_due_amount_calculation_blocked: MagicMock
    ):
        mock_is_due_amount_calculation_blocked.side_effect = [True, True]

        self.assertFalse(
            repayment_holiday.should_trigger_reamortisation_no_impact_preference(
                vault=sentinel.vault,
                period_start_datetime=sentinel.period_start_datetime,
                period_end_datetime=sentinel.period_end_datetime,
            )
        )
        mock_is_due_amount_calculation_blocked.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.vault,
                    effective_datetime=sentinel.period_start_datetime,
                ),
                call(
                    vault=sentinel.vault,
                    effective_datetime=sentinel.period_end_datetime,
                ),
            ]
        )
        self.assertEqual(mock_is_due_amount_calculation_blocked.call_count, 2)

    @patch.object(repayment_holiday.utils, "get_parameter")
    def test_with_preference_no_flag_at_period_start(
        self, mock_get_parameter: MagicMock, mock_is_due_amount_calculation_blocked: MagicMock
    ):
        mock_is_due_amount_calculation_blocked.return_value = False
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"repayment_holiday_impact_preference": "increase_emi"}
        )

        self.assertFalse(
            repayment_holiday.should_trigger_reamortisation_with_impact_preference(
                vault=sentinel.vault,
                period_start_datetime=sentinel.period_start_datetime,
                period_end_datetime=sentinel.period_end_datetime,
            )
        )
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=sentinel.period_start_datetime,
        )

    @patch.object(repayment_holiday.utils, "get_parameter")
    def test_with_preference_flag_at_period_start_not_at_end(
        self, mock_get_parameter: MagicMock, mock_is_due_amount_calculation_blocked: MagicMock
    ):
        mock_is_due_amount_calculation_blocked.side_effect = [True, False]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"repayment_holiday_impact_preference": "increase_emi"}
        )

        self.assertTrue(
            repayment_holiday.should_trigger_reamortisation_with_impact_preference(
                vault=sentinel.vault,
                period_start_datetime=sentinel.period_start_datetime,
                period_end_datetime=sentinel.period_end_datetime,
            )
        )
        mock_is_due_amount_calculation_blocked.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.vault,
                    effective_datetime=sentinel.period_start_datetime,
                ),
                call(
                    vault=sentinel.vault,
                    effective_datetime=sentinel.period_end_datetime,
                ),
            ]
        )
        self.assertEqual(mock_is_due_amount_calculation_blocked.call_count, 2)

    @patch.object(repayment_holiday.utils, "get_parameter")
    def test_with_preference_flag_at_period_start_and_end(
        self, mock_get_parameter: MagicMock, mock_is_due_amount_calculation_blocked: MagicMock
    ):
        mock_is_due_amount_calculation_blocked.side_effect = [True, True]
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"repayment_holiday_impact_preference": "increase_emi"}
        )

        self.assertFalse(
            repayment_holiday.should_trigger_reamortisation_with_impact_preference(
                vault=sentinel.vault,
                period_start_datetime=sentinel.period_start_datetime,
                period_end_datetime=sentinel.period_end_datetime,
            )
        )
        mock_is_due_amount_calculation_blocked.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.vault,
                    effective_datetime=sentinel.period_start_datetime,
                ),
                call(
                    vault=sentinel.vault,
                    effective_datetime=sentinel.period_end_datetime,
                ),
            ]
        )
        self.assertEqual(mock_is_due_amount_calculation_blocked.call_count, 2)

    @patch.object(repayment_holiday.utils, "get_parameter")
    def test_with_preference_increase_term(
        self, mock_get_parameter: MagicMock, mock_is_due_amount_calculation_blocked: MagicMock
    ):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"repayment_holiday_impact_preference": "increase_term"}
        )

        self.assertFalse(
            repayment_holiday.should_trigger_reamortisation_with_impact_preference(
                vault=sentinel.vault,
                period_start_datetime=sentinel.period_start_datetime,
                period_end_datetime=sentinel.period_end_datetime,
            )
        )
        mock_is_due_amount_calculation_blocked.assert_not_called()


@patch.object(repayment_holiday, "is_due_amount_calculation_blocked")
class SupervisorAmortisationTest(SupervisorFeatureTest):
    def test_no_preference_no_flag_at_period_start_supervisor(
        self, mock_is_due_amount_calculation_blocked: MagicMock
    ):
        mock_is_due_amount_calculation_blocked.return_value = False

        self.assertFalse(
            repayment_holiday.supervisor_should_trigger_reamortisation_no_impact_preference(
                loan_vault=sentinel.vault,
                main_vault=sentinel.main_vault,
                period_start_datetime=sentinel.period_start_datetime,
                period_end_datetime=sentinel.period_end_datetime,
            )
        )
        mock_is_due_amount_calculation_blocked.assert_called_once_with(
            vault=sentinel.main_vault,
            effective_datetime=sentinel.period_start_datetime,
        )

    def test_no_preference_flag_at_period_start_not_at_end_supervisor(
        self, mock_is_due_amount_calculation_blocked: MagicMock
    ):
        mock_is_due_amount_calculation_blocked.side_effect = [True, False]

        self.assertTrue(
            repayment_holiday.supervisor_should_trigger_reamortisation_no_impact_preference(
                loan_vault=sentinel.vault,
                main_vault=sentinel.main_vault,
                period_start_datetime=sentinel.period_start_datetime,
                period_end_datetime=sentinel.period_end_datetime,
            )
        )
        mock_is_due_amount_calculation_blocked.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.main_vault,
                    effective_datetime=sentinel.period_start_datetime,
                ),
                call(
                    vault=sentinel.main_vault,
                    effective_datetime=sentinel.period_end_datetime,
                ),
            ]
        )
        self.assertEqual(mock_is_due_amount_calculation_blocked.call_count, 2)

    def test_no_preference_flag_at_period_start_and_end_supervisor(
        self, mock_is_due_amount_calculation_blocked: MagicMock
    ):
        mock_is_due_amount_calculation_blocked.side_effect = [True, True]

        self.assertFalse(
            repayment_holiday.supervisor_should_trigger_reamortisation_no_impact_preference(
                loan_vault=sentinel.vault,
                main_vault=sentinel.main_vault,
                period_start_datetime=sentinel.period_start_datetime,
                period_end_datetime=sentinel.period_end_datetime,
            )
        )
        mock_is_due_amount_calculation_blocked.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.main_vault,
                    effective_datetime=sentinel.period_start_datetime,
                ),
                call(
                    vault=sentinel.main_vault,
                    effective_datetime=sentinel.period_end_datetime,
                ),
            ]
        )
        self.assertEqual(mock_is_due_amount_calculation_blocked.call_count, 2)


@patch.object(repayment_holiday.utils, "get_parameter")
class ImpactPreferenceTest(FeatureTest):
    def test_is_repayment_holiday_impact_increase_emi_false(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"repayment_holiday_impact_preference": "increase_term"}
        )

        self.assertFalse(
            repayment_holiday.is_repayment_holiday_impact_increase_emi(
                vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
            )
        )

    def test_is_repayment_holiday_impact_increase_emi_true(self, mock_get_parameter: MagicMock):
        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={"repayment_holiday_impact_preference": "increase_emi"}
        )

        self.assertTrue(
            repayment_holiday.is_repayment_holiday_impact_increase_emi(
                vault=sentinel.vault, effective_datetime=sentinel.effective_datetime
            )
        )
