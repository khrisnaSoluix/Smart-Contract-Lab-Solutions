# standard libs
from json import dumps
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.deposit.dormancy as dormancy

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
    construct_flag_timeseries,
    construct_parameter_timeseries,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    Rejection,
    RejectionReason,
)


class DormancyTest(FeatureTest):
    def test_account_dormant(self):
        # construct mocks
        mock_vault = self.create_mock(
            parameter_ts=construct_parameter_timeseries(
                parameter_name_to_value_map={
                    dormancy.PARAM_DORMANCY_FLAGS: dumps(["ACCOUNT_DORMANT"])
                },
                default_datetime=DEFAULT_DATETIME,
            ),
            flags_ts=construct_flag_timeseries(
                flag_name_to_bool_map={"ACCOUNT_DORMANT": True},
                default_datetime=DEFAULT_DATETIME,
            ),
        )

        # run function
        result = dormancy.is_account_dormant(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.assertEqual(result, True)

    def test_account_not_dormant(self):
        # construct mocks
        mock_vault = self.create_mock(
            parameter_ts=construct_parameter_timeseries(
                parameter_name_to_value_map={
                    dormancy.PARAM_DORMANCY_FLAGS: dumps(["ACCOUNT_DORMANT"])
                },
                default_datetime=DEFAULT_DATETIME,
            ),
            flags_ts=construct_flag_timeseries(
                flag_name_to_bool_map={"ACCOUNT_DORMANT": False},
                default_datetime=DEFAULT_DATETIME,
            ),
        )

        # run function
        result = dormancy.is_account_dormant(
            vault=mock_vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.assertEqual(result, False)

    @patch.object(dormancy, "is_account_dormant")
    def test_validate_account_transaction_with_account_dormant(
        self,
        mock_is_account_dormant: MagicMock,
    ):
        # construct values
        mock_is_account_dormant.return_value = True
        expected_result = Rejection(
            message="Account flagged 'Dormant' does not accept external transactions.",
            reason_code=RejectionReason.AGAINST_TNC,
        )

        # run function
        result = dormancy.validate_account_transaction(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.assertEqual(result, expected_result)

        # call assertions
        mock_is_account_dormant.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
        )

    @patch.object(dormancy, "is_account_dormant")
    def test_validate_account_transaction_with_account_not_dormant(
        self,
        mock_is_account_dormant: MagicMock,
    ):
        # construct values
        mock_is_account_dormant.return_value = False

        # run function
        result = dormancy.validate_account_transaction(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
        )
        self.assertIsNone(result)

        # call assertions
        mock_is_account_dormant.assert_called_once_with(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
        )
