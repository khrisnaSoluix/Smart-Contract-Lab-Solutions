# Copyright @ 2020-2023 Thought Machine Group Limited. All rights reserved.
# standard libs
import sys
import unittest
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions

from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractModuleConfig,
    ExpectedDerivedParameter,
    ExpectedRejection,
    SimulationTestScenario,
    SubTest,
    ExpectedSchedule,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    SimulationEvent,
    create_account_instruction,
    create_auth_adjustment_instruction,
    create_flag_definition_event,
    create_flag_event,
    create_inbound_authorisation_instruction,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_authorisation_instruction,
    create_outbound_hard_settlement_instruction,
    create_posting_instruction_batch,
    create_settlement_event,
    create_template_parameter_change_event,
    create_transfer_instruction,
    update_account_status_pending_closure,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
    get_balances,
    get_logs,
    get_num_postings,
    get_processed_scheduled_events,
)
from inception_sdk.vault.postings.posting_classes import (
    InboundHardSettlement,
    OutboundHardSettlement,
)

####TODO: Remove after debugging####
import logging
log = logging.getLogger(
    "inception_sdk.test_framework.contracts.simulation.vault_caller.sim_test_response_logger"
)
handler = logging.FileHandler(
    "/tmp/log.json", mode="w"
)
log.propagate = False # comment this out if you do not want printing to stdout
log.addHandler(handler)
log.setLevel(logging.DEBUG)
handler.setLevel(logging.DEBUG)
####TODO: Remove after debugging####

CONTRACT_FILE = "exercise/bcas/saving_accounts/contracts/template/saving_accounts_exercise_6.py"
ASSET_CONTRACT_FILE = "exercise/bcas/common/internal_accounts/contracts/asset_account_contract.py"
LIABILITY_CONTRACT_FILE = (
    "exercise/bcas/common/internal_accounts/contracts/liability_account_contract.py"
)

CONTRACT_MODULES_ALIAS_FILE_MAP = {}

BASIC_EXAMPLE_CONTRACT_VERSION_ID = "1000"

CONTRACT_FILES = [CONTRACT_FILE]

ACCOUNT_NAME = "Main account"

INTERNAL_ACCOUNTS_DICT = {
    # This is a generic account used for external postings
    "1": "LIABILITY",
    "ACCRUE_INTEREST_INTERTAL_ACCOUNT":"LIABILITY",
    "BONUS_PAYABLE_INTERNAL_ACCOUNT":"LIABILITY",
    "ZAKAT_INTERNAL_ACCOUNT":"LIABILITY",
}

default_simulation_start_date = datetime(
    year=2024, month=5, day=8, tzinfo=timezone.utc
)

DEFAULT_INTERNAL_ACCOUNT = "1"
DEFAULT_DEPOSIT_BONUS_PAYOUT_INTERNAL_ACCOUNT = "BONUS_PAYABLE_INTERNAL_ACCOUNT"
DEFAULT_ACCRUE_INTEREST_INTERNAL_ACCOUNT = "ACCRUE_INTEREST_INTERTAL_ACCOUNT"
DEFAULT_ZAKAT_INTERNAL_ACCOUNT = "ZAKAT_INTERNAL_ACCOUNT"
DEFAULT_OPENING_BONUS = "100"
DEFAULT_FLAG_FREEZE_ACCOUNT = "FREEZE_ACCOUNT"
DEFAULT_ACCRUE_INTEREST = "ACCRUE_INTEREST"
DEFAULT_INTEREST_RATE = "0.01"
DEFAULT_ZAKAT_RATE = "0.02"
DEFAULT_MAXIMUM_BALANCE_LIMIT = "1000000"

# parameters
DEFAULT_DENOMINATION = "IDR"

DEFAULT_DIMENSIONS = BalanceDimensions(
    denomination=DEFAULT_DENOMINATION,
)

default_template_params = {
    "denomination": DEFAULT_DENOMINATION,
    "deposit_bonus_payout_internal_account": DEFAULT_DEPOSIT_BONUS_PAYOUT_INTERNAL_ACCOUNT,
    "accrue_interest_internal_account": DEFAULT_ACCRUE_INTEREST_INTERNAL_ACCOUNT,
    "zakat_internal_account": DEFAULT_ZAKAT_INTERNAL_ACCOUNT,
    "interest_rate": DEFAULT_INTEREST_RATE,
    "maximum_balance_limit":DEFAULT_MAXIMUM_BALANCE_LIMIT,
}
default_instance_params = {
    "opening_bonus": DEFAULT_OPENING_BONUS,
    "zakat_rate":DEFAULT_ZAKAT_RATE,
}


class SavingAccount(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepaths = CONTRACT_FILES
        cls.contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
        ]
        super().setUpClass()

    def _get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
        debug=True, # TODO: Revert to False after debugging is done
    ):
        contract_config = ContractConfig(
            contract_file_path=CONTRACT_FILE,
            template_params=template_params or default_template_params,
            smart_contract_version_id=BASIC_EXAMPLE_CONTRACT_VERSION_ID,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or default_instance_params,
                )
            ],
            linked_contract_modules=self.contract_modules,
        )
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=internal_accounts or INTERNAL_ACCOUNTS_DICT,
            debug=debug,
        )

    # Exercise 1 : Test opening bonuse
    def test_activation_releases_bonus(self):
        """
        Test that upon account activation, activation bonus is credited to account
        """
        start = default_simulation_start_date
        end = start + relativedelta(days=1)

        sub_tests = [
            SubTest(
                description="test bonus is released to account after activation",
                events=[],
                # DEFAULT balance should be Rp98 since it has been deducted by zakat for Rp2 for opening bonus
                expected_balances_at_ts={
                    start: {ACCOUNT_NAME: [(DEFAULT_DIMENSIONS, "98")]},
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)
        
    # Exercise 2 : Test reject wrong denomination
    def test_reject_wrong_denomination(self):
        """
        Test that posting denominations are checked and accepted or rejected where necessary
        """
        start = default_simulation_start_date
        end = start + relativedelta(days=1)

        sub_tests = [
            # DEFAULT balance should be Rp98 since it has been deducted by zakat for Rp2 for opening bonus
            # After inbound posting Rp1000 the DEFAULT balance should be Rp1098
            SubTest(
                description="test balance correct after single deposit made to account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        denomination="IDR",
                        amount="1000",
                        # posting at ( start + 1h )
                        event_datetime=start + relativedelta(hours=1),
                    ),
                ],
                expected_balances_at_ts={
                    # Before posting ( start + 59m59s )
                    start
                    + relativedelta(minutes=59, seconds=50): {
                        ACCOUNT_NAME: [(DEFAULT_DIMENSIONS, "98")]
                    },
                    # After posting ( start + 1h1s )
                    start
                    + relativedelta(hours=1, seconds=1): {
                        ACCOUNT_NAME: [(DEFAULT_DIMENSIONS, "1098")]
                    },
                },
            ),
            # DEFAULT balance should be Rp1098 since the posting has been rejected
            SubTest(
                description="test balance correct after deposit with wrong denomination is made",
                events=[
                    create_inbound_hard_settlement_instruction(
                        denomination="USD",
                        amount="1000",
                        # posting at ( start + 2h )
                        event_datetime=start + relativedelta(hours=2),
                    ),
                ],
                expected_balances_at_ts={
                    # Before posting ( start + 1h59m )
                    start
                    + relativedelta(hours=1, minutes=59): {
                        ACCOUNT_NAME: [(DEFAULT_DIMENSIONS, "1098")]
                    },
                    # After posting ( start + 2h1s )
                    start
                    + relativedelta(hours=2, seconds=1): {
                        ACCOUNT_NAME: [(DEFAULT_DIMENSIONS, "1098")]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + relativedelta(hours=2),
                        rejection_type="WrongDenomination",
                        rejection_reason=("Postings are not allowed. Only postings in IDR are accepted."),
                    )
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)
    
    # Exercise 3 : Test derived parameters
    def test_derived_parameters(self):
        """
        Test that derived parameters are calculated
        """
        start = default_simulation_start_date
        end = start + relativedelta(days=1)

        sub_tests = [
            SubTest(
                description="test that derived parameters are calculated properly",
                events=[],
                # Expected available_deposit_limit should be Rp1000000 - Rp98 = Rp999902
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        timestamp=end,
                        account_id=ACCOUNT_NAME,
                        value="999902",
                        name="available_deposit_limit",
                    )
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    # Exercise 4 : Test interest accrual schedule
    def test_interest_accrual_schedule(self):
        """
        Test that interest is applied correctly
        """
        start = default_simulation_start_date
        end = start + relativedelta(months=1, days=1)

        sub_tests = [
            SubTest(
                description="test interest accrual schedule",
                events=[
                    # top up account to accrue interest on
                    create_inbound_hard_settlement_instruction(
                        denomination="IDR",
                        amount="99902",
                        event_datetime=start + relativedelta(hours=1),
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[start + relativedelta(months=1, minute=10)],
                        event_id="ACCRUE_INTEREST",
                        account_id=ACCOUNT_NAME,
                    )
                ],
                # DEFAULT balance after posting should be  Rp100000
                # After interest accrual for 1 month the interest should be Rp93 
                # The final DEFAULT balance should be Rp100093
                expected_balances_at_ts={
                    start: {ACCOUNT_NAME: [(DEFAULT_DIMENSIONS, "98")]},
                    end: {ACCOUNT_NAME: [(DEFAULT_DIMENSIONS, "100093")]},
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)


if __name__ == "__main__":
    if any(item.startswith("test") for item in sys.argv):
        unittest.main(SavingAccount)
    else:
        unittest.main(SavingAccount())
