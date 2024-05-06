# standard libs
from unittest.mock import MagicMock, patch, sentinel

# features
from library.features.v4.common.test.mocks import mock_utils_get_parameter
from library.features.v4.lending import lending_parameters

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest


@patch.object(lending_parameters.utils, "get_parameter")
class GetParametersTest(FeatureTest):
    def test_get_total_repayment_count_parameter(self, mock_get_parameter: MagicMock):
        total_repayment_count_parameter = 5

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                lending_parameters.PARAM_TOTAL_REPAYMENT_COUNT: total_repayment_count_parameter
            },
        )

        result = lending_parameters.get_total_repayment_count_parameter(vault=sentinel.vault)

        self.assertEqual(
            total_repayment_count_parameter,
            result,
        )
