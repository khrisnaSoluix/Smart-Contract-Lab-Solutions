# standard libs
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal

# contracts api
from contracts_api import NumberShape

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    SimulationEvent,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.events.parameter_events import (
    CreateGlobalParameterEvent,
    CreateGlobalParameterValue,
    GlobalParameter,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_inbound_hard_settlement_instruction,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase

default_simulation_start_date = datetime(year=2021, month=1, day=11, tzinfo=timezone.utc)
CONTRACT_FILE = (
    "inception_sdk/test_framework/contracts/simulation/test/mock_product/global_params_sc.py"
)
DENOMINATION = "GBP"
# Internal account addresses
ACCRUED_INTEREST_PAYABLE = "ACCRUED_INTEREST_PAYABLE"
_1 = "1"

INTERNAL_ACCOUNTS_TSIDE: dict = {
    ACCRUED_INTEREST_PAYABLE: "LIABILITY",
    _1: "LIABILITY",
}
DEFAULT_DIMENSIONS = BalanceDimensions()
ACCRUED_INTEREST_PAYABLE_DIMENSION = BalanceDimensions(
    address=ACCRUED_INTEREST_PAYABLE, denomination=DENOMINATION
)
CASH_RATE_PARAM = "cash_rate"


class GlobalParamsTest(SimulationTestCase):
    @classmethod
    def setUpClass(self):
        self.contract_file_path = CONTRACT_FILE
        self.contract_modules = []
        super().setUpClass()

    def _get_contract_config(
        self,
        template_params: dict = None,
        instance_params: dict = None,
    ) -> ContractConfig:
        template_params = template_params or {}
        instance_params = instance_params or {}
        return ContractConfig(
            contract_file_path=CONTRACT_FILE,
            template_params=template_params,
            smart_contract_version_id="1000",
            account_configs=[AccountConfig(instance_params=instance_params)],
            linked_contract_modules=[],
            global_params=[
                CreateGlobalParameterEvent(
                    global_parameter=GlobalParameter(
                        id=CASH_RATE_PARAM,
                        display_name="Cash Rate",
                        description="Central bank overnight lending interest rate.",
                        number=NumberShape(
                            min_value=Decimal(0),
                            max_value=Decimal(1),
                            step=Decimal("0.0001"),
                        ),
                        str=None,
                        denomination=None,
                        date=None,
                    ),
                    initial_value=Decimal("0.01"),
                ),
            ],
        )

    def test_global_param_read(self):
        start = default_simulation_start_date
        end = default_simulation_start_date + relativedelta(days=1, hours=2)
        opening_balance = Decimal(1000000)
        sub_tests = [
            SubTest(
                description="Set opening balance.",
                events=[
                    create_inbound_hard_settlement_instruction(str(opening_balance), start),
                ],
                expected_balances_at_ts={
                    start: {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, opening_balance),
                            (ACCRUED_INTEREST_PAYABLE_DIMENSION, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Test balance correct after first day interest accrual.",
                events=[],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1, seconds=1): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, opening_balance),
                            (ACCRUED_INTEREST_PAYABLE_DIMENSION, Decimal("27.39726")),
                        ]
                    },
                },
            ),
            SubTest(
                description="Update cash rate.",
                events=[
                    SimulationEvent(
                        time=start + relativedelta(hours=14),
                        event=CreateGlobalParameterValue(
                            global_parameter_id=CASH_RATE_PARAM,
                            value=Decimal("0.03"),
                            effective_timestamp=start + relativedelta(hours=16),
                        ).to_dict(),
                    )
                ],
            ),
            SubTest(
                description="Test balance correct after second day interest accrual.",
                events=[],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1, hours=1, seconds=1): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, opening_balance),
                            (ACCRUED_INTEREST_PAYABLE_DIMENSION, Decimal("109.58904")),
                        ]
                    }
                },
            ),
        ]

        test_scenario = SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=self._get_contract_config(),
            internal_accounts=INTERNAL_ACCOUNTS_TSIDE,
        )
        self.run_test_scenario(test_scenario)


# flake8: noqa
