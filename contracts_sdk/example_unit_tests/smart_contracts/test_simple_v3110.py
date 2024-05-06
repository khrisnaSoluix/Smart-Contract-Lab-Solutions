from datetime import datetime
import os

from ...utils.tools import SmartContracts3110TestCase


class SimpleTestCase(SmartContracts3110TestCase):
    filepath = os.environ.get(
        "DATA_SIMPLE_V3110", "contracts_sdk/example_unit_tests/smart_contracts/simple_v3110.py"
    )
    contract_code = SmartContracts3110TestCase.load_contract_code(filepath)

    effective_date = datetime(year=2020, month=2, day=20)

    def test_scheduled_code_skip_event_type_schedule(self):
        self.run_contract_function(
            self.contract_code, "scheduled_code", "SKIP_EVENT_TYPE", self.effective_date
        )

        self.vault.update_event_type.assert_called_once_with(
            event_type="SKIP_EVENT_TYPE", skip=True
        )
