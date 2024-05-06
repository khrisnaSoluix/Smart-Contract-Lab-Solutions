# standard libs
from unittest.mock import MagicMock, patch, sentinel

# features
from library.features.common import common_parameters
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest


@patch.object(common_parameters.utils, "get_parameter")
class GetParametersTest(FeatureTest):
    def test_get_denomination_parameter(self, mock_get_parameter: MagicMock):
        denomination_parameter = "GBP"

        mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={common_parameters.PARAM_DENOMINATION: denomination_parameter},
        )

        result = common_parameters.get_denomination_parameter(vault=sentinel.vault)

        self.assertEqual(
            denomination_parameter,
            result,
        )
