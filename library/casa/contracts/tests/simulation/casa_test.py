# Copyright @ 2020-2022 Thought Machine Group Limited. All rights reserved.
# standard libs
import sys
import unittest
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from json import dumps
from typing import Dict, List
from unittest import skip

# common
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.vault.postings.posting_classes import (
    InboundHardSettlement,
    OutboundHardSettlement,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
    get_balances,
    get_logs,
    get_num_postings,
    get_processed_scheduled_events,
)
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractModuleConfig,
    ExpectedDerivedParameter,
    ExpectedRejection,
    ExpectedWorkflow,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    SimulationEvent,
    create_account_instruction,
    create_posting_instruction_batch,
    create_auth_adjustment_instruction,
    create_flag_definition_event,
    create_flag_event,
    create_inbound_authorisation_instruction,
    create_inbound_hard_settlement_instruction,
    create_outbound_authorisation_instruction,
    create_outbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_template_parameter_change_event,
    create_settlement_event,
    create_transfer_instruction,
    update_account_status_pending_closure,
)


CONTRACT_FILE = "library/casa/contracts/casa.py"
ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"

CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "utils": "library/common/contract_modules/utils.py",
    "interest": "library/common/contract_modules/interest.py",
}

CONTRACT_FILES = [CONTRACT_FILE]
DEFAULT_DIMENSIONS = BalanceDimensions()
ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS = BalanceDimensions(address="ACCRUED_OVERDRAFT_RECEIVABLE")

ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS = BalanceDimensions(
    address="ACCRUED_OVERDRAFT_FEE_RECEIVABLE"
)
ACCRUED_DEPOSIT_RECEIVABLE_DIMENSIONS = BalanceDimensions(address="ACCRUED_DEPOSIT_RECEIVABLE")
ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS = BalanceDimensions(address="ACCRUED_DEPOSIT_PAYABLE")

DORMANCY_FLAG = "ACCOUNT_DORMANT"
CASA_CONTRACT_VERSION_ID = "1000"

ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
OVERDRAFT_FEE_INCOME_ACCOUNT = "OVERDRAFT_FEE_INCOME"
OVERDRAFT_FEE_RECEIVABLE_ACCOUNT = "OVERDRAFT_FEE_RECEIVABLE"
MAINTENANCE_FEE_INCOME_ACCOUNT = "MAINTENANCE_FEE_INCOME"
MINIMUM_BALANCE_FEE_INCOME_ACCOUNT = "MINIMUM_BALANCE_FEE_INCOME"
ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT = "ANNUAL_MAINTENANCE_FEE_INCOME"
INACTIVITY_FEE_INCOME_ACCOUNT = "INACTIVITY_FEE_INCOME"
EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT = "EXCESS_WITHDRAWAL_FEE_INCOME"
TEST_SAVINGS_ACCOUNT = "test_savings_account"

INTERNAL_ACCOUNTS_DICT = {
    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: "ASSET",
    INTEREST_RECEIVED_ACCOUNT: "LIABILITY",
    ACCRUED_INTEREST_PAYABLE_ACCOUNT: "LIABILITY",
    INTEREST_PAID_ACCOUNT: "ASSET",
    OVERDRAFT_FEE_INCOME_ACCOUNT: "LIABILITY",
    OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: "ASSET",
    MAINTENANCE_FEE_INCOME_ACCOUNT: "LIABILITY",
    MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: "LIABILITY",
    ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: "LIABILITY",
    INACTIVITY_FEE_INCOME_ACCOUNT: "LIABILITY",
    EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT: "LIABILITY",
    TEST_SAVINGS_ACCOUNT: "LIABILITY",
    # This is a generic account used for external postings
    "1": "LIABILITY",
}

default_simulation_start_date = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)

default_template_params = {
    "denomination": "GBP",
    "additional_denominations": dumps(["USD", "EUR"]),
    "account_tier_names": dumps(
        [
            "CASA_TIER_UPPER",
            "CASA_TIER_MIDDLE",
            "CASA_TIER_LOWER",
        ]
    ),
    "deposit_interest_application_frequency": "monthly",
    "interest_accrual_days_in_year": "365",
    "interest_free_buffer": dumps(
        {
            "CASA_TIER_UPPER": "500",
            "CASA_TIER_MIDDLE": "300",
            "CASA_TIER_LOWER": "50",
        }
    ),
    "overdraft_interest_free_buffer_days": dumps(
        {
            "CASA_TIER_UPPER": "-1",
            "CASA_TIER_MIDDLE": "21",
            "CASA_TIER_LOWER": "-1",
        }
    ),
    "overdraft_interest_rate": "0.1485",
    "unarranged_overdraft_fee": "5",
    "unarranged_overdraft_fee_cap": "80",
    "interest_application_hour": "0",
    "interest_application_minute": "1",
    "interest_application_second": "0",
    "interest_accrual_hour": "0",
    "interest_accrual_minute": "0",
    "interest_accrual_second": "0",
    "accrued_interest_receivable_account": ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    "interest_received_account": INTEREST_RECEIVED_ACCOUNT,
    "accrued_interest_payable_account": ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    "interest_paid_account": INTEREST_PAID_ACCOUNT,
    "overdraft_fee_income_account": OVERDRAFT_FEE_INCOME_ACCOUNT,
    "overdraft_fee_receivable_account": OVERDRAFT_FEE_RECEIVABLE_ACCOUNT,
    "maintenance_fee_income_account": MAINTENANCE_FEE_INCOME_ACCOUNT,
    "minimum_balance_fee_income_account": MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
    "annual_maintenance_fee_income_account": ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT,
    "inactivity_fee_income_account": INACTIVITY_FEE_INCOME_ACCOUNT,
    "excess_withdrawal_fee_income_account": EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
    "maintenance_fee_annual": "0",
    "maintenance_fee_monthly": "0",
    "minimum_balance_threshold": dumps(
        {
            "CASA_TIER_UPPER": "25",
            "CASA_TIER_MIDDLE": "75",
            "CASA_TIER_LOWER": "100",
        }
    ),
    "minimum_balance_fee": "0",
    "account_inactivity_fee": "0",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "maximum_daily_atm_withdrawal_limit": dumps(
        {
            "CASA_TIER_UPPER": "5000",
            "CASA_TIER_MIDDLE": "2000",
            "CASA_TIER_LOWER": "1000",
        }
    ),
    "transaction_code_to_type_map": dumps({"": "purchase", "6011": "ATM withdrawal"}),
    "deposit_tier_ranges": dumps(
        {
            "tier1": {"min": "0"},
            "tier2": {"min": "3000.00"},
            "tier3": {"min": "5000.00"},
            "tier4": {"min": "7500.00"},
            "tier5": {"min": "15000.00"},
        }
    ),
    "deposit_interest_rate_tiers": dumps(
        {
            "tier1": "0.05",
            "tier2": "0.04",
            "tier3": "0.02",
            "tier4": "0",
            "tier5": "-0.035",
        }
    ),
    "autosave_rounding_amount": "1.00",
    "maximum_daily_withdrawal": "10000",
    "maximum_daily_deposit": "10000",
    "minimum_deposit": "0",
    "minimum_withdrawal": "0",
    "maximum_balance": "100000",
    "reject_excess_withdrawals": "false",
    "monthly_withdrawal_limit": "-1",
    "excess_withdrawal_fee": "0",
}

default_instance_params = {
    "arranged_overdraft_limit": "1000",
    "unarranged_overdraft_limit": "2000",
    "interest_application_day": "1",
    "daily_atm_withdrawal_limit": "1000",
}


class CASATest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepaths = CONTRACT_FILES
        cls.contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
        ]
        super().setUpClass()

    def default_create_account_instruction(self, start, instance_param_vals=None):
        return create_account_instruction(
            timestamp=start,
            account_id="Main account",
            product_id=CASA_CONTRACT_VERSION_ID,
            instance_param_vals=instance_param_vals or default_instance_params,
        )

    def run_test(
        self,
        start: datetime,
        end: datetime,
        events: List,
        template_parameters: Dict[str, str] = None,
    ):

        contract_config = ContractConfig(
            contract_file_path=CONTRACT_FILE,
            template_params=default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=default_instance_params,
                    account_id_base="Main account",
                )
            ],
            smart_contract_version_id=CASA_CONTRACT_VERSION_ID,
            linked_contract_modules=self.contract_modules,
        )

        return self.client.simulate_smart_contract(
            contract_codes=self.smart_contract_contents.copy(),
            smart_contract_version_ids=[CASA_CONTRACT_VERSION_ID],
            start_timestamp=start,
            end_timestamp=end,
            templates_parameters=[
                template_parameters or default_template_params,
            ],
            internal_account_ids=INTERNAL_ACCOUNTS_DICT,
            events=events,
            contract_config=contract_config,
        )

    def _get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
    ):
        contract_config = ContractConfig(
            contract_file_path=CONTRACT_FILE,
            template_params=template_params or default_template_params,
            smart_contract_version_id=CASA_CONTRACT_VERSION_ID,
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
        )

    def test_deposits_with_multiple_denominations(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=1)

        sub_tests = [
            SubTest(
                description="test balance correct after single deposit made to account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "283.45", start + relativedelta(hours=1)
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1, seconds=1): {
                        "Main account": [(DEFAULT_DIMENSIONS, "283.45")]
                    },
                },
            ),
            SubTest(
                description="test balance correct after multiple deposits made to account",
                events=[
                    create_inbound_hard_settlement_instruction("100", start + timedelta(hours=2)),
                    create_inbound_hard_settlement_instruction("100", start + timedelta(hours=3)),
                    create_inbound_hard_settlement_instruction(
                        "100.45", start + timedelta(hours=4)
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=4, seconds=1): {
                        "Main account": [(DEFAULT_DIMENSIONS, "583.90")]
                    },
                },
            ),
            SubTest(
                description="test mix denomination inbound payments",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100", start + timedelta(hours=5), denomination="EUR"
                    ),
                    create_inbound_hard_settlement_instruction(
                        "120", start + timedelta(hours=6), denomination="USD"
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=6, seconds=1): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "583.90"),
                            (BalanceDimensions(denomination="EUR"), "100"),
                            (BalanceDimensions(denomination="USD"), "120"),
                        ]
                    },
                },
            ),
            SubTest(
                description="test mix denomination outbound payment",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "50", start + timedelta(hours=7), denomination="USD"
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=7, seconds=1): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "583.90"),
                            (BalanceDimensions(denomination="EUR"), "100"),
                            (BalanceDimensions(denomination="USD"), "70"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Ensure additional currencies cannot go negative",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "101", start + timedelta(hours=8), denomination="EUR"
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=8, seconds=1): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "583.90"),
                            (BalanceDimensions(denomination="EUR"), "100"),
                            (BalanceDimensions(denomination="USD"), "70"),
                        ]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=8),
                        account_id="Main account",
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total EUR -101, which "
                        "exceeds the available balance of EUR 100",
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

    def test_overdraft_limit_and_unsupported_denom_rejected(self):
        start = default_simulation_start_date
        end = start + relativedelta(days=1)

        withdrawal_instruction_1999_GBP = OutboundHardSettlement(
            target_account_id="Main account",
            amount="1999",
            denomination=default_template_params["denomination"],
        )

        withdrawal_instruction_5_GBP = OutboundHardSettlement(
            target_account_id="Main account",
            amount="5",
            denomination=default_template_params["denomination"],
        )

        withdrawal_instruction_90_EUR = OutboundHardSettlement(
            target_account_id="Main account",
            amount="90",
            denomination="EUR",
        )

        deposit_instruction_100_EUR = InboundHardSettlement(
            target_account_id="Main account",
            amount="100",
            denomination="EUR",
        )

        deposit_instruction_120_USD = InboundHardSettlement(
            target_account_id="Main account",
            amount="120",
            denomination="USD",
        )

        deposit_instruction_100_CNY = InboundHardSettlement(
            target_account_id="Main account",
            amount="100",
            denomination="CNY",
        )

        sub_tests = [
            SubTest(
                description="Test entire batch is rejected if main denom outside overdraft limit",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            withdrawal_instruction_1999_GBP,
                            withdrawal_instruction_5_GBP,
                            deposit_instruction_100_EUR,
                            deposit_instruction_120_USD,
                        ],
                        event_datetime=start + timedelta(hours=1),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=1, seconds=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="EUR"), "0"),
                            (BalanceDimensions(denomination="GBP"), "0"),
                            (BalanceDimensions(denomination="USD"), "0"),
                        ]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=1),
                        account_id="Main account",
                        rejection_type="InsufficientFunds",
                        rejection_reason="Posting exceeds unarranged_overdraft_limit",
                    )
                ],
            ),
            SubTest(
                description="Test entire batch rejected if unsupported denom present",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            withdrawal_instruction_1999_GBP,
                            deposit_instruction_100_CNY,
                            deposit_instruction_100_EUR,
                            deposit_instruction_120_USD,
                        ],
                        event_datetime=start + timedelta(hours=2),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2, seconds=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="EUR"), "0"),
                            (BalanceDimensions(denomination="GBP"), "0"),
                            (BalanceDimensions(denomination="USD"), "0"),
                            (BalanceDimensions(denomination="CNY"), "0"),
                        ]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=2),
                        account_id="Main account",
                        rejection_type="WrongDenomination",
                        rejection_reason="Postings received in unauthorised denomination CNY.",
                    )
                ],
            ),
            SubTest(
                description="test entire batch is accepted if credits greater than debits",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            withdrawal_instruction_90_EUR,
                            deposit_instruction_100_EUR,
                        ],
                        event_datetime=start + timedelta(hours=3),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=3, seconds=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="EUR"), "10"),
                        ]
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    @skip("sim incorrectly executes pre-posting for settlements")
    def test_negative_balance_will_reject_subsequent_outbound_and_accept_inbound(self):
        """Due to the way the postings interface works, if an authorisation is oversettled,
        the account balance may go into the negative."""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=12, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                "100", start + timedelta(hours=1), denomination="EUR"
            ),
            create_outbound_authorisation_instruction(
                "50",
                start + timedelta(hours=2),
                denomination="EUR",
                client_transaction_id="12",
            ),
            create_settlement_event(
                "50",
                event_datetime=start + timedelta(hours=3),
                client_transaction_id="12",
                final=False,
            ),
            create_settlement_event(
                "60",
                event_datetime=start + timedelta(hours=4),
                client_transaction_id="12",
                final=True,
            ),
            create_outbound_hard_settlement_instruction(
                "100", start + timedelta(hours=5), denomination="EUR"
            ),
            create_inbound_hard_settlement_instruction(
                "100", start + timedelta(hours=6), denomination="EUR"
            ),
        ]

        res = self.run_test(start, end, events)

        self.assertIn(
            "Postings total EUR -100, which exceeds the available balance of EUR -10",
            get_logs(res),
        )

        expected_balances = {
            "Main account": {
                end: [
                    (
                        BalanceDimensions(denomination="EUR", phase="POSTING_PHASE_COMMITTED"),
                        "90",
                    )
                ]
            }
        }

        self.check_balances(actual_balances=get_balances(res), expected_balances=expected_balances)

    def test_outbound_authorisations_adjustment_rejected(self):

        start = default_simulation_start_date
        end = start + relativedelta(days=1)

        sub_tests = [
            SubTest(
                description="Ensure outbound authorisations reduce available balance,"
                "but inbound authorisations do not increase available balance",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100", start + timedelta(hours=1), denomination="EUR"
                    ),
                    create_outbound_authorisation_instruction(
                        "50", start + timedelta(hours=2), denomination="EUR"
                    ),
                    create_inbound_authorisation_instruction(
                        "50", start + timedelta(hours=3), denomination="EUR"
                    ),
                    create_outbound_hard_settlement_instruction(
                        "60", start + timedelta(hours=4), denomination="EUR"
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=3, seconds=1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    denomination="EUR", phase="POSTING_PHASE_COMMITTED"
                                ),
                                "100",
                            ),
                            (
                                BalanceDimensions(
                                    denomination="EUR",
                                    phase="POSTING_PHASE_PENDING_OUTGOING",
                                ),
                                "-50",
                            ),
                            (
                                BalanceDimensions(
                                    denomination="EUR",
                                    phase="POSTING_PHASE_PENDING_INCOMING",
                                ),
                                "50",
                            ),
                        ]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=4),
                        account_id="Main account",
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total EUR -60, "
                        "which exceeds the available balance of EUR 50",
                    )
                ],
            ),
            SubTest(
                description="Test authorisation adjustments cannot cause negative balances",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100", start + timedelta(hours=5), denomination="USD"
                    ),
                    create_outbound_authorisation_instruction(
                        "50",
                        start + timedelta(hours=6),
                        denomination="USD",
                        client_transaction_id="12",
                    ),
                    create_auth_adjustment_instruction(
                        "60",
                        event_datetime=start + timedelta(hours=7),
                        client_transaction_id="12",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=7, seconds=1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    denomination="USD", phase="POSTING_PHASE_COMMITTED"
                                ),
                                "100",
                            ),
                            (
                                BalanceDimensions(
                                    denomination="USD",
                                    phase="POSTING_PHASE_PENDING_OUTGOING",
                                ),
                                "-50",
                            ),
                        ]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=7),
                        account_id="Main account",
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total USD -60, "
                        "which exceeds the available balance of USD 50",
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

    def test_entire_batch_is_rejected_and_atm_limits(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, hour=1, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="entire PIB rejected as one of it's PIs exceeds ATM withdrawl limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "2500", start + timedelta(hours=1), denomination="EUR"
                    ),
                    create_inbound_hard_settlement_instruction(
                        "2500", start + timedelta(hours=2), denomination="GBP"
                    ),
                    # GBP withdrawal exceeds ATM limits
                    SimulationEvent(
                        start + timedelta(hours=3),
                        {
                            "create_posting_instruction_batch": {
                                "client_id": "Visa",
                                "client_batch_id": "111",
                                "posting_instructions": [
                                    {
                                        "outbound_hard_settlement": {
                                            "amount": "2000",
                                            "denomination": "GBP",
                                            "target_account": {"account_id": "Main account"},
                                            "internal_account_id": "1",
                                            "advice": False,
                                        },
                                        "client_transaction_id": "test_1",
                                        "instruction_details": {"transaction_code": "6011"},
                                    },
                                    {
                                        "inbound_hard_settlement": {
                                            "amount": "2095",
                                            "denomination": "EUR",
                                            "target_account": {"account_id": "Main account"},
                                            "internal_account_id": "1",
                                            "advice": False,
                                        },
                                        "client_transaction_id": "test_2",
                                        "instruction_details": {"transaction_code": "3212"},
                                    },
                                ],
                                "batch_details": {"description": "none"},
                                "value_timestamp": datetime.isoformat(start + timedelta(hours=3)),
                            }
                        },
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=6): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    denomination="EUR", phase="POSTING_PHASE_COMMITTED"
                                ),
                                "2500",
                            ),
                            (
                                BalanceDimensions(
                                    denomination="GBP",
                                    phase="POSTING_PHASE_COMMITTED",
                                ),
                                "2500",
                            ),
                        ]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=3),
                        account_id="Main account",
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction would cause the ATM daily withdrawal limit "
                        "of 1000 GBP to be exceeded.",
                    )
                ],
            ),
            SubTest(
                description="small ATM withdrawal to exceed daily withdrawal limit is rejected",
                events=[
                    # Initial transaction within limits should be accepted
                    create_outbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(hours=8),
                        instruction_details={"transaction_code": "6011"},
                    ),
                    # A deposit should not affect limits
                    create_inbound_hard_settlement_instruction("100", start + timedelta(hours=9)),
                    # Transaction beyond limits should be rejected
                    create_outbound_hard_settlement_instruction(
                        "5",
                        start + timedelta(hours=10),
                        instruction_details={"transaction_code": "6011"},
                    ),
                    # Different transaction type should still go through
                    create_outbound_hard_settlement_instruction(
                        "50",
                        start + timedelta(hours=11),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=11): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    denomination="GBP",
                                    phase="POSTING_PHASE_COMMITTED",
                                ),
                                "1550",
                            ),
                        ]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=10),
                        account_id="Main account",
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction would cause the ATM daily withdrawal limit "
                        "of 1000 GBP to be exceeded.",
                    )
                ],
            ),
            SubTest(
                description="ATM withdrawal limit does not apply to the additional currencies",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "2000",
                        start + timedelta(hours=12),
                        denomination="EUR",
                        instruction_details={"transaction_code": "6011"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=12): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    denomination="EUR",
                                    phase="POSTING_PHASE_COMMITTED",
                                ),
                                "500",
                            ),
                        ]
                    },
                },
            ),
            SubTest(
                description="ATM withdrawal limit resets at midnight",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(days=1, minutes=1),
                        denomination="GBP",
                        instruction_details={"transaction_code": "6011"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=1, minutes=1): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "550"),
                        ]
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )
        res = self.run_test_scenario(test_scenario)

        self.assertEqual(get_num_postings(res, "Main account"), 7)

    def test_arranged_and_unarranged_overdrafts(self):
        start = datetime(year=2018, month=12, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=4, day=2, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Check no overdraft interest accrued if not in overdraft.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "400",
                        start + relativedelta(hours=1),
                    ),
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + relativedelta(hours=2),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(hours=2): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "100"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "0"),
                        ],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: {
                            (DEFAULT_DIMENSIONS, "0"),
                        },
                        INTEREST_RECEIVED_ACCOUNT: {(DEFAULT_DIMENSIONS, "0")},
                    },
                    start
                    + relativedelta(days=30): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "100"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "0"),
                        ],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: {
                            (DEFAULT_DIMENSIONS, "0"),
                        },
                        INTEREST_RECEIVED_ACCOUNT: {(DEFAULT_DIMENSIONS, "0")},
                    },
                    start
                    + relativedelta(months=1, minutes=1): {
                        "Main account": [
                            # Some interest accrued on deposit gets applied
                            (DEFAULT_DIMENSIONS, "100.42"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "0"),
                        ],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: {
                            (DEFAULT_DIMENSIONS, "0"),
                        },
                        INTEREST_RECEIVED_ACCOUNT: {(DEFAULT_DIMENSIONS, "0")},
                    },
                },
            ),
            SubTest(
                description="Arranged overdraft accrues interest then remainder is netted off when "
                " interest is applied and no fees are charged",
                events=[
                    # clear previous month's balance
                    create_outbound_hard_settlement_instruction(
                        amount="100.42", event_datetime=start + relativedelta(months=1, hours=5)
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="450", event_datetime=start + relativedelta(months=1, hours=7)
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, microseconds=-1): {
                        # This overdraft will be rounded down to 2 d.p. (as -5.04) leaving a
                        # remainder of 0.00494
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-450"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-5.04494"),
                            (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "0"),
                        ],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: {
                            (DEFAULT_DIMENSIONS, "5.04494"),
                        },
                        INTEREST_RECEIVED_ACCOUNT: {(DEFAULT_DIMENSIONS, "5.04494")},
                    },
                    start
                    + relativedelta(months=2, minutes=1): {
                        # The accrued interest is returned to 0 after interest is applied with no
                        # remainder left over
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-455.04"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "0"),
                            (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "0"),
                        ],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: {(DEFAULT_DIMENSIONS, "0")},
                        INTEREST_RECEIVED_ACCOUNT: {(DEFAULT_DIMENSIONS, "5.04")},
                    },
                },
            ),
            SubTest(
                description="Test accrual of unarranged overdraft interest, fee is charged "
                "interest isn't accrued against fee",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="1543.96", event_datetime=start + relativedelta(months=2, minutes=2)
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=2, minutes=2): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-1999"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "0"),
                            (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "0"),
                            (BalanceDimensions(address="INTERNAL_CONTRA"), "0"),
                        ],
                        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (DEFAULT_DIMENSIONS, "0"),
                        ],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (DEFAULT_DIMENSIONS, "0"),
                        ],
                    },
                    start
                    + relativedelta(months=2, days=1, minutes=2): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-1999"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-0.79295"),
                            (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "-5"),
                            (BalanceDimensions(address="INTERNAL_CONTRA"), "5.79295"),
                        ],
                        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (DEFAULT_DIMENSIONS, "5"),
                        ],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (DEFAULT_DIMENSIONS, "5"),
                        ],
                    },
                    start
                    + relativedelta(months=2, days=2, minutes=2): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-1999"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-1.58590"),
                            (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "-10"),
                            (BalanceDimensions(address="INTERNAL_CONTRA"), "11.58590"),
                        ],
                        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (DEFAULT_DIMENSIONS, "10"),
                        ],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (DEFAULT_DIMENSIONS, "10"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Application of unarranged overdraft interest and fee is capped at £80",
                expected_balances_at_ts={
                    start
                    + relativedelta(months=3): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-1999"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-22.20260"),
                            (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "-80"),
                            (BalanceDimensions(address="INTERNAL_CONTRA"), "102.20260"),
                        ],
                        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (DEFAULT_DIMENSIONS, "80"),
                        ],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (DEFAULT_DIMENSIONS, "80"),
                        ],
                    },
                    start
                    + relativedelta(months=3, minutes=1): {
                        # Charged 22.20 for overdraft interest + 80 max overdraft fees
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-2101.20"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "0"),
                            (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "0"),
                            (BalanceDimensions(address="INTERNAL_CONTRA"), "0"),
                        ],
                        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (DEFAULT_DIMENSIONS, "0"),
                        ],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (DEFAULT_DIMENSIONS, "80"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Overdraft interest is accrued based on overdraft "
                "at end of day, not maximum overdraft over the course of the day",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "2201.20",
                        start + relativedelta(months=3, hours=1),
                    ),
                    create_outbound_hard_settlement_instruction(
                        "400",
                        start + relativedelta(months=3, hours=2),
                    ),
                    create_outbound_hard_settlement_instruction(
                        "200",
                        start + relativedelta(months=3, hours=3),
                    ),
                    # End overdraft at 300
                    create_inbound_hard_settlement_instruction(
                        "200",
                        start + relativedelta(months=3, hours=4),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(months=3, days=1, minutes=1): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-300"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-0.10171"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_overdraft_interest_free_buffer(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        buffer_end_1 = datetime(year=2019, month=1, day=4, tzinfo=timezone.utc)
        buffer_reset = datetime(year=2019, month=1, day=7, hour=9, tzinfo=timezone.utc)
        buffer_end_2 = datetime(year=2019, month=1, day=11, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=14, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "account_tier_names": dumps(["X"]),
            "interest_free_buffer": dumps({"X": "50"}),
            "overdraft_interest_free_buffer_days": dumps({"X": "3"}),
        }

        sub_tests = [
            SubTest(
                description="Ensure no overdraft interest is accrued during the buffer days and "
                "overdraft interest is accrued after the buffer days",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "30",
                        start + timedelta(hours=1),
                    ),
                ],
                expected_balances_at_ts={
                    buffer_end_1: {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-30"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "0"),
                        ]
                    },
                    buffer_end_1
                    + relativedelta(days=3): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-30"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-0.03663"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Ensure overdraft interest is accrued during the buffer days on amount "
                "over buffer and accrued on total on days after the buffer days",
                events=[
                    # reset balance to 0 so buffer days reset at midnight
                    create_inbound_hard_settlement_instruction(
                        "30",
                        buffer_reset,
                    ),
                    create_outbound_hard_settlement_instruction(
                        "100",
                        buffer_reset + relativedelta(days=1),
                    ),
                ],
                expected_balances_at_ts={
                    buffer_end_2: {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-100"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-0.09765"),
                        ]
                    },
                    end: {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-100"),
                            # Interest accrues faster after the buffer ends as full balance accrues
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-0.21969"),
                        ]
                    },
                },
            ),
        ]

        self._get_simulation_test_scenario(
            start=start,
            end=end,
            template_params=template_params,
            sub_tests=sub_tests,
        )

    def test_multiple_and_expired_flag_behaviour(self):
        """
        Check that if multiple flags are applied, the first active in the tier_names is used.
        Once the flag expires, the next active flag in the list is applied
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=2, tzinfo=timezone.utc)
        flag_1_expiry = start + timedelta(days=31, hours=1)
        template_params = {
            **default_template_params,
            "account_tier_names": dumps(["X", "Y", "Z"]),
            "interest_free_buffer": dumps({"X": "25", "Y": "150.00", "Z": "0"}),
            "overdraft_interest_free_buffer_days": dumps({"X": "0", "Y": "-1", "Z": "0"}),
        }

        events = [
            create_flag_definition_event(timestamp=start, flag_definition_id="Y"),
            create_flag_definition_event(timestamp=start, flag_definition_id="Z"),
            self.default_create_account_instruction(start),
            create_flag_event(
                timestamp=start,
                expiry_timestamp=flag_1_expiry,
                flag_definition_id="Y",
                account_id="Main account",
            ),
            create_flag_event(
                timestamp=start,
                expiry_timestamp=end,
                flag_definition_id="Z",
                account_id="Main account",
            ),
            create_outbound_hard_settlement_instruction(amount="130", event_datetime=start),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                # Until this point the active tier has -1 buffer days, so no interest is charged
                flag_1_expiry: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "-130"),
                        (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "0"),
                    ]
                },
                # Expired tier has no effect, new tier has 0 buffer days so interest is charged
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "-130"),
                        # OD interest rate 0.1485
                        (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-0.05289"),
                    ]
                },
            },
        )

    def test_overdraft_accrual_one_year(self):
        """
        Test that overdraft is accrued correctly over a year
        including interest on overdraft fee.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        events = [
            self.default_create_account_instruction(start),
            create_outbound_hard_settlement_instruction(amount="1500", event_datetime=start),
        ]

        res = self.run_test(start, end, events)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "Main account": {
                    end: [
                        (DEFAULT_DIMENSIONS, "-2646.32"),
                        (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "-80"),
                        (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-32.74561"),
                    ]
                }
            },
        )

    def test_decimal_arranged_overdraft(self):
        """Test that overdraft interest is charged even if only in overdraft by 0.1"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        events = [
            self.default_create_account_instruction(start),
            create_outbound_hard_settlement_instruction(amount="50.1", event_datetime=start),
        ]

        res = self.run_test(start, end, events)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "Main account": {
                    end: [
                        (DEFAULT_DIMENSIONS, "-50.1"),
                        (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-.00004"),
                    ]
                }
            },
        )

    def test_decimal_unarranged_overdraft(self):
        """Test that the overdraft fee is applied even if only in unarranged overdraft by 0.01."""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        events = [
            self.default_create_account_instruction(start),
            create_outbound_hard_settlement_instruction(amount="1000.1", event_datetime=start),
        ]

        res = self.run_test(start, end, events)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "Main account": {
                    end: [
                        (DEFAULT_DIMENSIONS, "-1000.1"),
                        (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "-5"),
                    ]
                }
            },
        )

    def test_monthly_maintenance_fee_is_applied(self):
        """Test that the monthly maintenance fee is applied"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        before_final_apply = datetime(year=2019, month=3, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=1, minute=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maintenance_fee_monthly": "10",
        }

        events = [
            self.default_create_account_instruction(start),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                before_final_apply: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "-10"),
                    ],
                    MAINTENANCE_FEE_INCOME_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "10"),
                    ],
                },
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "-20"),
                    ],
                    MAINTENANCE_FEE_INCOME_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "20"),
                    ],
                },
            },
        )

    def test_monthly_maintenance_fee_not_applied_if_zero(self):
        """Test that the monthly maintenance fee is not applied if fee is zero"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        before_final_apply = datetime(year=2019, month=3, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=1, minute=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maintenance_fee_monthly": "0",
        }

        events = [
            self.default_create_account_instruction(start),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                before_final_apply: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "0"),
                    ],
                    MAINTENANCE_FEE_INCOME_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0"),
                    ],
                },
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "0"),
                    ],
                    MAINTENANCE_FEE_INCOME_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0"),
                    ],
                },
            },
        )

    def test_monthly_maintenance_fee_min_balance_and_overdraft_fee_are_applied(self):
        """Test that the monthly maintenance fee, min balance fee and overdraft fees are applied"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maintenance_fee_monthly": "10",
            "minimum_balance_fee": "25",
        }

        events = [
            self.default_create_account_instruction(start),
            create_outbound_hard_settlement_instruction(
                "500",
                start + timedelta(hours=1),
            ),
            create_inbound_hard_settlement_instruction(
                "600",
                start + timedelta(hours=2),
            ),
            create_outbound_hard_settlement_instruction(
                "1200",
                start + timedelta(hours=3),
            ),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "-1228.24"),
                    ],
                    MAINTENANCE_FEE_INCOME_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "10"),
                    ],
                    MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "25"),
                    ],
                    OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "5"),
                    ],
                    OVERDRAFT_FEE_INCOME_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "85"),
                    ],
                },
            },
        )

    def test_min_balance_applied_if_mean_balance_is_zero(self):
        """Test that the min balance fee is applied if mean balance is zero"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maintenance_fee_monthly": "0",
            "minimum_balance_fee": "25",
        }

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                "50",
                start + timedelta(days=2),
            ),
            create_outbound_hard_settlement_instruction(
                "50",
                start + timedelta(days=2, hours=1),
            ),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "-25"),
                    ],
                    MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "25"),
                    ],
                },
            },
        )

    def test_min_balance_applied_if_mean_balance_is_sampling_in_leap_year_february(
        self,
    ):
        """Test that the min balance fee is applied if mean balance is zero"""
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=3, day=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maintenance_fee_monthly": "0",
            "minimum_balance_fee": "25",
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
        }
        # The mean balance is sampled daily for a month at the fee application time. Set up balances
        # which are:
        # - just below the balance threshold during the current sampling month
        # - well above the balance threshold before and after the sampling month
        # such that if the sampling month included the outlying balances the test would fail by
        # the mean being above the threshold and not charging the fee.
        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                "450",
                start,
            ),
            create_outbound_hard_settlement_instruction(
                "401",
                start + timedelta(days=31, hours=1),
            ),
            create_inbound_hard_settlement_instruction(
                "401",
                end - timedelta(hours=1),
            ),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "425"),
                    ],
                    MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "25"),
                    ],
                },
            },
        )

    def test_annual_maintenance_fee_is_applied_and_triggers_internal_account_movements(
        self,
    ):
        """Test that the annual maintenance fee is applied"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        before_apply = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=1, minute=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maintenance_fee_annual": "75",
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
        }

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(amount="100", event_datetime=start),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                before_apply: {
                    "Main account": [(DEFAULT_DIMENSIONS, "100")],
                    ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                },
                end: {
                    "Main account": [(DEFAULT_DIMENSIONS, "25")],
                    ANNUAL_MAINTENANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "75")],
                },
            },
        )

    def test_maintenance_fee_application_time_with_internal_account_movements(self):
        """Test that the maintenance fee is applied at the configured time"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        before_apply = datetime(
            year=2019,
            month=3,
            day=1,
            hour=17,
            minute=30,
            second=29,
            tzinfo=timezone.utc,
        )
        end = datetime(
            year=2019,
            month=3,
            day=1,
            hour=17,
            minute=30,
            second=31,
            tzinfo=timezone.utc,
        )
        template_params = {
            **default_template_params,
            "maintenance_fee_monthly": "10",
            "fees_application_hour": "17",
            "fees_application_minute": "30",
            "fees_application_second": "30",
        }

        events = [
            self.default_create_account_instruction(start),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                before_apply: {
                    "Main account": [(DEFAULT_DIMENSIONS, "-10")],
                    MAINTENANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "10")],
                },
                end: {
                    "Main account": [(DEFAULT_DIMENSIONS, "-20")],
                    MAINTENANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "20")],
                },
            },
        )

    def test_positive_deposit_interest_accrued_and_applied_with_internal_account_movements(
        self,
    ):
        """
        Check positive deposit interest is accrued based on deposit balance
        at midnight and subsequently applied, with correct internal account movements
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        eod1 = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=1, minute=1, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="1000", event_datetime=start + timedelta(hours=1)
            ),
            create_outbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(hours=2)
            ),
            create_outbound_hard_settlement_instruction(
                amount="200", event_datetime=start + timedelta(hours=3)
            ),
        ]

        res = self.run_test(start, end, events)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                eod1: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "700"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0.09589"),
                    ],
                    ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "0.09589")],
                    INTEREST_PAID_ACCOUNT: [(DEFAULT_DIMENSIONS, "0.09589")],
                },
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "702.97"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                    ],
                    ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                    INTEREST_PAID_ACCOUNT: [(DEFAULT_DIMENSIONS, "2.97")],
                },
            },
        )

    def test_positive_deposit_interest_accrual_application_actual_year_during_leap_year(
        self,
    ):
        """
        Check to ensure the positive accrued deposit balance is applied.
        End midway through month 2 day 1 to ensure interest application at eod
        and no interest has been accrued (to ensure reversals are correct)
        with actual year calculation (366 days)
        """
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=2, day=1, hour=12, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "interest_accrual_days_in_year": "actual",
        }

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(amount="1000", event_datetime=start),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1004.23"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                    ],
                    ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                    INTEREST_PAID_ACCOUNT: [(DEFAULT_DIMENSIONS, "4.23")],
                }
            },
        )

    def test_negative_deposit_interest_accrued_and_applied_with_internal_account_movements(
        self,
    ):
        """
        Check negative deposit interest is accrued based on deposit balance
        at midnight and subsequently applied, with correct internal account movements
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        eod1 = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=1, minute=1, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "deposit_interest_rate_tiers": dumps({"tier1": "-0.05"}),
        }

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="1000", event_datetime=start + timedelta(hours=1)
            ),
            create_outbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(hours=2)
            ),
            create_outbound_hard_settlement_instruction(
                amount="200", event_datetime=start + timedelta(hours=3)
            ),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                eod1: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "700"),
                        (ACCRUED_DEPOSIT_RECEIVABLE_DIMENSIONS, "-0.09589"),
                    ],
                    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "0.09589")],
                    INTEREST_RECEIVED_ACCOUNT: [(DEFAULT_DIMENSIONS, "0.09589")],
                },
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "697.03"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                    ],
                    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                    INTEREST_RECEIVED_ACCOUNT: [(DEFAULT_DIMENSIONS, "2.97")],
                },
            },
        )

    def test_negative_deposit_interest_accrued_and_applied_360_year(self):
        """
        Check negative deposit interest is accrued based on deposit balance
        at midnight and subsequently applied, with correct internal account movements
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, minute=1, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "interest_accrual_days_in_year": "360",
            "deposit_interest_rate_tiers": dumps({"tier1": "-0.03"}),
        }

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="1000", event_datetime=start + timedelta(hours=1)
            ),
            create_outbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(hours=2)
            ),
            create_outbound_hard_settlement_instruction(
                amount="200", event_datetime=start + timedelta(hours=3)
            ),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "700"),
                        (ACCRUED_DEPOSIT_RECEIVABLE_DIMENSIONS, "-0.05833"),
                    ],
                    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "0.05833")],
                    INTEREST_RECEIVED_ACCOUNT: [(DEFAULT_DIMENSIONS, "0.05833")],
                }
            },
        )

    def test_deposit_interest_rate_change_from_positive_to_negative(self):
        """
        Check accrual works correctly when moving from a positive interest rate
        to a negative interest rate.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        rate_change_date = start + timedelta(days=10, hours=2)
        pre_apply = datetime(year=2019, month=1, day=29, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=1, minute=1, tzinfo=timezone.utc)
        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="1000", event_datetime=start + timedelta(hours=1)
            ),
            create_template_parameter_change_event(
                timestamp=rate_change_date,
                smart_contract_version_id=CASA_CONTRACT_VERSION_ID,
                deposit_interest_rate_tiers=dumps({"tier1": "-0.05"}),
            ),
        ]

        res = self.run_test(start, end, events)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                rate_change_date: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1000"),
                        # 10 accruals at 0.05
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "1.3699"),
                    ],
                    ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "1.3699"),
                    ],
                    INTEREST_PAID_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "1.3699"),
                    ],
                    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0"),
                    ],
                    INTEREST_RECEIVED_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0"),
                    ],
                },
                pre_apply: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1000"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "1.3699"),
                        # 18 accruals at -0.05
                        (ACCRUED_DEPOSIT_RECEIVABLE_DIMENSIONS, "-2.46582"),
                    ],
                    ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "1.3699"),
                    ],
                    INTEREST_PAID_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "1.3699"),
                    ],
                    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "2.46582"),
                    ],
                    INTEREST_RECEIVED_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "2.46582"),
                    ],
                },
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "998.49"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                        # 19 accruals at -0.05
                        (ACCRUED_DEPOSIT_RECEIVABLE_DIMENSIONS, "0"),
                    ],
                    ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0"),
                    ],
                    INTEREST_PAID_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "1.37"),
                    ],
                    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0"),
                    ],
                    INTEREST_RECEIVED_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "2.88"),
                    ],
                },
            },
        )

    def test_deposit_interest_zero_rate_accrual_with_internal_account_movements(self):
        """
        Check accrual does not accrue any deposit interest when interest rate is set to zero.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=10, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
        }

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="1000", event_datetime=start + timedelta(hours=1)
            ),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1000"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                    ],
                    ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                    INTEREST_PAID_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                }
            },
        )

    def test_positive_deposit_interest_with_overdraft_with_internal_account_movements(
        self,
    ):
        """
        Check to ensure the accrued balances are with a mix of deposit and overdraft
        interest applied.
        End midway through month 2 to ensure interest application at eod
        and no interest has been accrued (to ensure reversals are correct)
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        deposit_to_od_date = start + timedelta(days=5, hours=2)
        od_to_deposit_date = start + timedelta(days=20, hours=2)
        end = datetime(year=2019, month=2, day=1, hour=12, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            # Balance 1000 | Deposit Interest on 1000 @ 5% | 5 Days
            create_inbound_hard_settlement_instruction(amount="1000", event_datetime=start),
            # Balance -200 | O.D. Interest on 150 @ 14.85% | 15 Days
            create_outbound_hard_settlement_instruction(
                amount="1200", event_datetime=deposit_to_od_date
            ),
            # Balance 2800 | Deposit Interest on 2800 @ 5% | 10 Days
            create_inbound_hard_settlement_instruction(
                amount="3000", event_datetime=od_to_deposit_date
            ),
        ]

        res = self.run_test(start, end, events)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                start: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1000"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0.0"),
                    ]
                },
                deposit_to_od_date: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "-200"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0.68495"),
                    ],
                    ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0.68495"),
                    ],
                    INTEREST_PAID_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0.68495"),
                    ],
                    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0"),
                    ],
                    INTEREST_RECEIVED_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0"),
                    ],
                },
                od_to_deposit_date: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "2800"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0.68495"),
                        (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-0.91545"),
                    ],
                    ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0.68495"),
                    ],
                    INTEREST_PAID_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0.68495"),
                    ],
                    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0.91545"),
                    ],
                    INTEREST_RECEIVED_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0.91545"),
                    ],
                },
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "2803.98"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                        (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "0"),
                    ],
                    ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0"),
                    ],
                    INTEREST_PAID_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "4.9"),
                    ],
                    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0"),
                    ],
                    INTEREST_RECEIVED_ACCOUNT: [
                        (DEFAULT_DIMENSIONS, "0.92"),
                    ],
                },
            },
        )

    def test_interest_accrued_and_applied_at_configurable_time(self):
        """
        Ensure the configurable interest accrual and application time works
        Overdraft and deposit interest time is derived from the same parameter.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=2, tzinfo=timezone.utc)
        first_accrual = datetime(2019, 1, 1, 22, 58, 56, 999999, tzinfo=timezone.utc)
        first_apply = datetime(2019, 2, 1, 20, 59, 1, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "interest_accrual_hour": "22",
            "interest_accrual_minute": "58",
            "interest_accrual_second": "57",
            "interest_application_hour": "20",
            "interest_application_minute": "59",
            "interest_application_second": "1",
        }

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(amount="1000", event_datetime=start),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                first_accrual
                - timedelta(microseconds=1): {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1000"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0.0"),
                    ]
                },
                first_accrual: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1000"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0.13699"),
                    ]
                },
                first_apply
                - timedelta(microseconds=1): {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1000"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "4.24669"),
                    ]
                },
                first_apply: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1004.25"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                    ]
                },
            },
        )

    def test_interest_applied_annually(self):
        """
        Ensure annual interest application works
        """
        start = datetime(year=2019, month=1, day=5, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=11, tzinfo=timezone.utc)
        apply = datetime(2020, 1, 10, 20, 59, 1, tzinfo=timezone.utc)

        instance_params = {
            **default_instance_params,
            "interest_application_day": "10",
        }
        template_params = {
            **default_template_params,
            "deposit_interest_application_frequency": "annually",
            "interest_application_hour": "20",
            "interest_application_minute": "59",
            "interest_application_second": "1",
        }

        events = [
            self.default_create_account_instruction(start, instance_params),
            create_inbound_hard_settlement_instruction(amount="1000", event_datetime=start),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                apply
                - timedelta(microseconds=1): {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1000"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "50.6863"),
                    ]
                },
                apply: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1050.69"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                    ]
                },
            },
        )

    def test_interest_applied_quarterly_at_configurable_time(self):
        """
        Ensure the configurable interest accrual and application time works
        Overdraft and deposit interest time is derived from the same parameter.
        """
        start = datetime(year=2019, month=1, day=5, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=5, tzinfo=timezone.utc)
        first_apply = datetime(2019, 4, 4, 20, 59, 1, tzinfo=timezone.utc)
        second_apply = datetime(2019, 7, 4, 20, 59, 1, tzinfo=timezone.utc)
        third_apply = datetime(2019, 10, 4, 20, 59, 1, tzinfo=timezone.utc)
        fourth_apply = datetime(2020, 1, 4, 20, 59, 1, tzinfo=timezone.utc)

        instance_params = {
            **default_instance_params,
            "interest_application_day": "4",
        }
        template_params = {
            **default_template_params,
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.05"}),
            "deposit_interest_application_frequency": "quarterly",
            "interest_application_hour": "20",
            "interest_application_minute": "59",
            "interest_application_second": "1",
        }

        events = [
            self.default_create_account_instruction(start, instance_params),
            create_inbound_hard_settlement_instruction(amount="1000", event_datetime=start),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                first_apply
                - timedelta(microseconds=1): {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1000"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "12.19211"),
                    ]
                },
                first_apply: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1012.19"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                    ]
                },
                second_apply
                - timedelta(microseconds=1): {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1012.19"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "12.61806"),
                    ]
                },
                second_apply: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1024.81"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                    ]
                },
                third_apply
                - timedelta(microseconds=1): {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1024.81"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "12.91496"),
                    ]
                },
                third_apply: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1037.72"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                    ]
                },
                fourth_apply
                - timedelta(microseconds=1): {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1037.72"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "13.0778"),
                    ]
                },
                fourth_apply: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1050.8"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                    ]
                },
            },
        )

    def test_mixed_tiered_interest_accrued_with_internal_account_movements(self):
        """
        Test tiered interest with different interest rates at different amounts.
        The default tiering tests positive, zero and negative interest rates.
        """
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        first_accrual = datetime(year=2020, month=1, day=2, tzinfo=timezone.utc)
        end = datetime(year=2020, month=2, day=1, hour=10, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "20000",
        }
        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(amount="20000", event_datetime=start),
        ]

        res = self.run_test(start, end, events, template_params)

        # Individual accruals are 0.41096 + 0.21918 + 0.13699 + 0 - 0.47945
        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                first_accrual: {
                    "Main account": [
                        (BalanceDimensions(), "20000"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0.76713"),
                        (ACCRUED_DEPOSIT_RECEIVABLE_DIMENSIONS, "-0.47945"),
                    ],
                    ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(BalanceDimensions(), "0.76713")],
                    INTEREST_PAID_ACCOUNT: [(BalanceDimensions(), "0.76713")],
                    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [(BalanceDimensions(), "0.47945")],
                    INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(), "0.47945")],
                },
                end
                - timedelta(days=1): {
                    "Main account": [
                        (BalanceDimensions(), "20000"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "23.01390"),
                        (ACCRUED_DEPOSIT_RECEIVABLE_DIMENSIONS, "-14.38350"),
                    ],
                    ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(BalanceDimensions(), "23.01390")],
                    INTEREST_PAID_ACCOUNT: [(BalanceDimensions(), "23.01390")],
                    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [(BalanceDimensions(), "14.38350")],
                    INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(), "14.38350")],
                },
                # additional accrual before application of payable = 0.76713 and
                # receivable = 0.47945
                end: {
                    "Main account": [
                        (BalanceDimensions(), "20008.92"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                        (ACCRUED_DEPOSIT_RECEIVABLE_DIMENSIONS, "0"),
                    ],
                    ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(BalanceDimensions(), "0")],
                    INTEREST_PAID_ACCOUNT: [(BalanceDimensions(), "23.78")],
                    ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [(BalanceDimensions(), "0")],
                    INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(), "14.86")],
                },
            },
        )

    def test_minimum_balance_below_threshold_with_midnight_sampling_no_flag(self):
        """
        Mean balance below threshold in sampling period and so fee charged.
        Above threshold before and after to check period.
        Sampling time at midnight
        Check internal account movements for min balance fee income account
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=2, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "minimum_balance_fee": "100",
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
        }

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(amount="200", event_datetime=start),
            create_outbound_hard_settlement_instruction(
                amount="100",
                event_datetime=datetime(year=2019, month=1, day=31, hour=23, tzinfo=timezone.utc),
            ),
            create_outbound_hard_settlement_instruction(
                amount="1",
                event_datetime=datetime(year=2019, month=2, day=27, hour=23, tzinfo=timezone.utc),
            ),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "-1"),
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                    ],
                    MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "100")],
                }
            },
        )

    def test_minimum_balance_below_threshold_with_midnight_sampling_with_flag(self):
        """
        Check the account flag is used to extract tiered minimum balance,
        including that if there are multiple flags, the lowest index one is used..

        Other MAB tests check the correct default tier is used when no flag is
        set for the account.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=2, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "minimum_balance_fee": "100",
            "account_tier_names": dumps(["X", "Y", "Z"]),
            "minimum_balance_threshold": dumps({"X": "1.5", "Y": "100", "Z": "200"}),
            "interest_free_buffer": dumps({"X": "500", "Y": "300", "Z": "50"}),
            "overdraft_interest_free_buffer_days": dumps({"X": "-1", "Y": "21", "Z": "-1"}),
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
        }

        events = [
            create_flag_definition_event(timestamp=start, flag_definition_id="X"),
            create_flag_definition_event(timestamp=start, flag_definition_id="Y"),
            self.default_create_account_instruction(start),
            create_flag_event(
                timestamp=start,
                expiry_timestamp=end,
                flag_definition_id="X",
                account_id="Main account",
            ),
            create_flag_event(
                timestamp=start,
                expiry_timestamp=end,
                flag_definition_id="Y",
                account_id="Main account",
            ),
            create_inbound_hard_settlement_instruction(amount="1.75", event_datetime=start),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                # no fee is charged as tier X has 1.5 minimum balance
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "1.75"),
                    ],
                    MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                }
            },
        )

    def test_expired_flags_no_longer_have_minimum_balance_tier_effect(self):
        """
        Check that an expired flag is no longer considered for tiering
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=2, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "minimum_balance_fee": "100",
            "account_tier_names": dumps(["X", "Y", "Z"]),
            "minimum_balance_threshold": dumps({"X": "1.5", "Y": "100", "Z": "200"}),
            "interest_free_buffer": dumps({"X": "500", "Y": "300", "Z": "50"}),
            "overdraft_interest_free_buffer_days": dumps({"X": "-1", "Y": "21", "Z": "-1"}),
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
        }

        events = [
            create_flag_definition_event(timestamp=start, flag_definition_id="X"),
            self.default_create_account_instruction(start),
            create_flag_event(
                timestamp=start,
                expiry_timestamp=start + timedelta(days=30),
                flag_definition_id="X",
                account_id="Main account",
            ),
            create_inbound_hard_settlement_instruction(amount="1.75", event_datetime=start),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                # fee is charged as tier defaults to Z and min balance is 200. Min balance for
                # expired tier X was 1.5, but this is no longer considered
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "-98.25"),
                    ],
                    MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "100")],
                }
            },
        )

    def test_minimum_balance_fee_applied_if_balance_below_threshold_with_day_end_sampling(
        self,
    ):
        """
        Mean balance below threshold in sampling period and so fee charged.
        Sampling time near the end of the day, before midnight
        Transaction on last day of month included because sampling at end of day
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=2, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "minimum_balance_fee": "100",
            "account_tier_names": dumps(["X"]),
            "minimum_balance_threshold": dumps({"X": "100"}),
            "interest_free_buffer": dumps({"X": "500"}),
            "overdraft_interest_free_buffer_days": dumps({"X": "-1"}),
            "fees_application_hour": "23",
            "fees_application_minute": "59",
            "fees_application_second": "58",
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
        }

        events = [
            self.default_create_account_instruction(start),
            # Deposit on account opening keeps above MAB for Jan,
            # then at the beginning of the next period the balance dips below £100
            create_inbound_hard_settlement_instruction(amount="200", event_datetime=start),
            create_outbound_hard_settlement_instruction(
                amount="101.01",
                event_datetime=datetime(year=2019, month=1, day=31, hour=23, tzinfo=timezone.utc),
            ),
        ]

        # At the start of the sampling period the balance is £98.99
        # It then oscillates between (£100.99, £98.99)
        # Because there are an even number of days in February and we started on £98.99,
        # the average is below £100
        for i in range(1, 29):
            if i % 2:
                posting_method = create_inbound_hard_settlement_instruction
            else:
                posting_method = create_outbound_hard_settlement_instruction

            events.append(
                posting_method(
                    amount="2",
                    event_datetime=datetime(
                        year=2019, month=2, day=i, hour=21, tzinfo=timezone.utc
                    ),
                )
            )
            # Add extra postings that cancel each other out to make sure they
            # don't affect calculation
            events.append(
                create_inbound_hard_settlement_instruction(
                    amount="1000",
                    event_datetime=datetime(
                        year=2019, month=2, day=i, hour=22, tzinfo=timezone.utc
                    ),
                )
            ),
            events.append(
                create_outbound_hard_settlement_instruction(
                    amount="1000",
                    event_datetime=datetime(
                        year=2019, month=2, day=i, hour=23, tzinfo=timezone.utc
                    ),
                )
            )
        # Another posting after the sampling period doesn't affect the mean balance
        events.append(
            create_inbound_hard_settlement_instruction(
                amount="100",
                event_datetime=datetime(
                    2019, 2, 28, hour=23, minute=59, second=59, tzinfo=timezone.utc
                ),
            )
        )

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                # no fee is charged as tier X has -1 minimum balance
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "98.99"),
                    ],
                    MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "100")],
                }
            },
        )

    def test_minimum_balance_fee_not_applied_midnight(self):
        """
        Mean balance below threshold after sampling period and so no fee charged.
        Sampling time time at midnight.
        Transaction on last day of month not included until next month because
        sampling at start of day.
        Simulate the account being opened at 3pm on the first day to make sure
        a missing sample doesn't adversely affect the mean
        """
        start = datetime(year=2019, month=1, day=1, hour=15, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=2, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "minimum_balance_fee": "100",
            "account_tier_names": dumps(["X"]),
            "minimum_balance_threshold": dumps({"X": "100"}),
            "interest_free_buffer": dumps({"X": "500"}),
            "overdraft_interest_free_buffer_days": dumps({"X": "-1"}),
            "fees_application_hour": "0",
            "fees_application_minute": "0",
            "fees_application_second": "0",
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
        }

        events = [
            self.default_create_account_instruction(start),
            # Deposit on account opening keeps above MAB for Jan.
            # Balance equals MAB for most of Feb, then dips below on last day but after sampling
            #  time --> no MAB fee charged
            create_inbound_hard_settlement_instruction(amount="100", event_datetime=start),
            create_outbound_hard_settlement_instruction(
                amount="1",
                # Feb monthly fee sampling ends on 2019-02-28T00:00:00Z
                event_datetime=datetime(2019, 2, 28, hour=23, minute=50, tzinfo=timezone.utc),
            ),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                # no fee is charged as tier X has -1 minimum balance
                end: {
                    "Main account": [
                        (DEFAULT_DIMENSIONS, "99"),
                    ],
                    MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                }
            },
        )

    def test_dormant_account_postings_rejected(self):
        """
        All postings are rejected after the account becomes dormant
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        dormant = datetime(year=2019, month=1, day=3, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=6, tzinfo=timezone.utc)

        events = [
            create_flag_definition_event(start, DORMANCY_FLAG),
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction("100", dormant + timedelta(days=-1)),
            create_flag_event(
                timestamp=dormant,
                expiry_timestamp=end,
                flag_definition_id=DORMANCY_FLAG,
                account_id="Main account",
            ),
            # Expect these postings to be rejected as they are after the dormancy flag activated
            create_transfer_instruction(
                "100",
                creditor_target_account_id="1",
                debtor_target_account_id="Main account",
                event_datetime=dormant + timedelta(days=1),
            ),
            create_outbound_hard_settlement_instruction("1", dormant + timedelta(days=2)),
        ]

        res = self.run_test(start, end, events)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"Main account": {end: [(DEFAULT_DIMENSIONS, "100")]}},
        )
        self.assertEqual(get_num_postings(res, "Main account"), 1)

    def test_dormant_account_accrues_interest(self):
        """
        test that interest keeps accruing after account is flagged dormant
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        dormant = datetime(year=2019, month=1, day=3, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=6, tzinfo=timezone.utc)

        events = [
            create_flag_definition_event(start, DORMANCY_FLAG),
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction("100", start),
            create_flag_event(
                timestamp=dormant,
                expiry_timestamp=end,
                flag_definition_id=DORMANCY_FLAG,
                account_id="Main account",
            ),
        ]

        res = self.run_test(start, end, events)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "Main account": {
                    end: [
                        (DEFAULT_DIMENSIONS, "100"),
                        # 5 accruals at 5%
                        (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0.0685"),
                    ]
                }
            },
        )
        self.assertEqual(get_num_postings(res, "Main account"), 1)

    def test_dormant_account_charged_overdraft(self):
        """
        Test accrual and application of overdraft interest over
        a single month for a dormant account including the unarranged overdraft fee
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=1, hour=1, tzinfo=timezone.utc)
        final_accrue = datetime(year=2019, month=2, day=1, tzinfo=timezone.utc)
        dormant = start + timedelta(hours=2)

        template_params = {
            **default_template_params,
            "account_inactivity_fee": "0",
        }

        events = [
            create_flag_definition_event(start, DORMANCY_FLAG),
            self.default_create_account_instruction(start),
            create_outbound_hard_settlement_instruction("1599", start),
            create_flag_event(
                timestamp=dormant,
                expiry_timestamp=end,
                flag_definition_id=DORMANCY_FLAG,
                account_id="Main account",
            ),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "Main account": {
                    final_accrue: [
                        (DEFAULT_DIMENSIONS, "-1599"),
                        (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-19.53651"),
                    ],
                    end: [
                        (DEFAULT_DIMENSIONS, "-1698.54"),
                        (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "0"),
                        (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "0"),
                        (BalanceDimensions(address="INTERNAL_CONTRA"), "0"),
                    ],
                },
                OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: {
                    end: [
                        (DEFAULT_DIMENSIONS, "0"),
                    ]
                },
                OVERDRAFT_FEE_INCOME_ACCOUNT: {
                    end: [
                        (DEFAULT_DIMENSIONS, "80"),
                    ]
                },
            },
        )

    def test_dormant_account_fees(self):
        """
        Test that the monthly, annual maintenance and minimum account balance fees
        are not applied if account is dormant, and that the dormancy fee is
        applied
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        dormant = datetime(year=2019, month=1, day=3, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=2, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "maintenance_fee_monthly": "10",
            "maintenance_fee_annual": "75",
            "minimum_balance_fee": "15",
            "minimum_balance_threshold": dumps({"CASA_TIER_LOWER": "1001"}),
            "account_inactivity_fee": "99",
        }

        template_params["deposit_tier_ranges"] = dumps({"tier1": {"min": "0"}})
        template_params["deposit_interest_rate_tiers"] = dumps({"tier1": "0.00"})

        events = [
            create_flag_definition_event(start, DORMANCY_FLAG),
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction("1200", start),
            create_flag_event(
                timestamp=dormant,
                expiry_timestamp=end,
                flag_definition_id=DORMANCY_FLAG,
                account_id="Main account",
            ),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [(DEFAULT_DIMENSIONS, "12")],
                    INACTIVITY_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "1188")],
                    MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                    MAINTENANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                }
            },
        )

    def test_active_account_not_charged_inactivity_fee(self):
        """
        Test that an account that is not marked "Dormant" is not charged the dormancy fee
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=2, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "maintenance_fee_monthly": "10",
            "account_inactivity_fee": "15",
        }

        events = [
            self.default_create_account_instruction(start),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [(DEFAULT_DIMENSIONS, "-10")],
                    INACTIVITY_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                    MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                    MAINTENANCE_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "10")],
                }
            },
        )

    def test_autosave_basic(self):
        """
        For a normal purchase with enough balance the expected amount is saved
        """
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=2, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "autosave_rounding_amount": "1.00",
            "denomination": "GBP",
        }
        instance_parameters = {
            **default_instance_params,
            "autosave_savings_account": TEST_SAVINGS_ACCOUNT,
        }

        events = [
            self.default_create_account_instruction(start, instance_parameters),
            create_inbound_hard_settlement_instruction("1000.01", start + timedelta(hours=1)),
            create_outbound_hard_settlement_instruction("283.45", start + timedelta(hours=2)),
            create_outbound_hard_settlement_instruction("515.01", start + timedelta(hours=3)),
            create_outbound_hard_settlement_instruction("88", start + timedelta(hours=4)),
            # At this point remaining balance is 112.01 so autosave will not be allowed
            create_outbound_hard_settlement_instruction("112.01", start + timedelta(hours=5)),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [(DEFAULT_DIMENSIONS, "0")],
                    TEST_SAVINGS_ACCOUNT: [(DEFAULT_DIMENSIONS, "1.54")],
                }
            },
        )

    def test_autosave_non_default_denomination(self):
        """
        Check that with autosave enabled, a spend with non default denomination
        does not use autosave
        """

        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "autosave_rounding_amount": "1.00",
            "denomination": "GBP",
        }
        instance_parameters = {
            **default_instance_params,
            "autosave_savings_account": TEST_SAVINGS_ACCOUNT,
        }

        events = [
            self.default_create_account_instruction(start, instance_parameters),
            create_inbound_hard_settlement_instruction(
                "1000", start + timedelta(hours=1), denomination="EUR"
            ),
            create_outbound_hard_settlement_instruction(
                "283.45", start + timedelta(hours=1), denomination="EUR"
            ),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [
                        (BalanceDimensions(denomination="EUR"), "716.55"),
                        (DEFAULT_DIMENSIONS, "0"),
                    ],
                    TEST_SAVINGS_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                }
            },
        )

    def test_autosave_min_balance(self):
        """
        Check that with autosave enabled, autosave does not happen when there is
        a minimum_balance_fee
        """

        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "autosave_rounding_amount": "1.00",
            "denomination": "GBP",
            "minimum_balance_fee": "50",
        }
        instance_parameters = {
            **default_instance_params,
            "autosave_savings_account": TEST_SAVINGS_ACCOUNT,
        }

        events = [
            self.default_create_account_instruction(start, instance_parameters),
            create_inbound_hard_settlement_instruction("1000", start + timedelta(hours=1)),
            create_outbound_hard_settlement_instruction("283.45", start + timedelta(hours=2)),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [(DEFAULT_DIMENSIONS, "716.55")],
                    TEST_SAVINGS_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                }
            },
        )

    def test_autosave_other_rounding_amount(self):
        """
        Check other autosave_rounding_amount
        """

        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "autosave_rounding_amount": "2.50",
            "denomination": "GBP",
        }
        instance_parameters = {
            **default_instance_params,
            "autosave_savings_account": TEST_SAVINGS_ACCOUNT,
        }

        events = [
            self.default_create_account_instruction(start, instance_parameters),
            create_inbound_hard_settlement_instruction("10000", start + timedelta(hours=1)),
            create_outbound_hard_settlement_instruction("4800.2", start + timedelta(hours=2)),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [(DEFAULT_DIMENSIONS, "5197.5")],
                    TEST_SAVINGS_ACCOUNT: [(DEFAULT_DIMENSIONS, "2.3")],
                }
            },
        )

    def test_autosave_multiple_postings_batch(self):
        """
        Check autosave where there is a batch containing multiple purchase postings
        """

        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "autosave_rounding_amount": "2.50",
            "denomination": "GBP",
        }
        instance_parameters = {
            **default_instance_params,
            "autosave_savings_account": TEST_SAVINGS_ACCOUNT,
        }

        events = [
            self.default_create_account_instruction(start, instance_parameters),
            create_inbound_hard_settlement_instruction("1000", start + timedelta(hours=1)),
            SimulationEvent(
                start + timedelta(hours=3),
                {
                    "create_posting_instruction_batch": {
                        "client_id": "Visa",
                        "client_batch_id": "111",
                        "posting_instructions": [
                            {
                                "outbound_hard_settlement": {
                                    "amount": "99.05",
                                    "denomination": "GBP",
                                    "target_account": {"account_id": "Main account"},
                                    "internal_account_id": "1",
                                    "advice": False,
                                },
                                "client_transaction_id": "test_1",
                                "instruction_details": {"transaction_code": "1234"},
                            },
                            {
                                "outbound_hard_settlement": {
                                    "amount": "49.75",
                                    "denomination": "GBP",
                                    "target_account": {"account_id": "Main account"},
                                    "internal_account_id": "1",
                                    "advice": False,
                                },
                                "client_transaction_id": "test_4",
                                "instruction_details": {"transaction_code": "1234"},
                            },
                        ],
                        "value_timestamp": datetime.isoformat(start + timedelta(hours=3)),
                    }
                },
            ),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [(DEFAULT_DIMENSIONS, "850")],
                    TEST_SAVINGS_ACCOUNT: [(DEFAULT_DIMENSIONS, "1.2")],
                }
            },
        )

    def test_autosave_auth_then_settlement_only_applies_autosave_once(self):
        """
        For an authorisation then settlement of the full amount, the expected amount is saved
        """

        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "autosave_rounding_amount": "1.00",
            "denomination": "GBP",
        }
        instance_parameters = {
            **default_instance_params,
            "autosave_savings_account": TEST_SAVINGS_ACCOUNT,
        }

        events = [
            self.default_create_account_instruction(start, instance_parameters),
            create_inbound_hard_settlement_instruction("1000.01", start + timedelta(hours=1)),
            create_outbound_authorisation_instruction(
                "283.45", start + timedelta(hours=2), client_transaction_id="100"
            ),
            create_settlement_event(
                amount="283.45",
                client_transaction_id="100",
                event_datetime=start + timedelta(hours=3),
                final=True,
            ),
        ]

        res = self.run_test(start, end, events, template_parameters=template_params)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                end: {
                    "Main account": [(DEFAULT_DIMENSIONS, "716.01")],
                    TEST_SAVINGS_ACCOUNT: [(DEFAULT_DIMENSIONS, "0.55")],
                }
            },
        )

    def test_live_balance_overdraft_limit_backdated_posting(self):
        """
        Ensure the live balance is used for overdraft limit with backdated posting

        Scenerio:
        A overdraft limit with $2000 GBP with a starting balance of $0
        At processing_time=3:00 an outbound withdrawn is made for $1999
        At processing_time=4:00 a backdated outbound withdrawn is made
        with a value timestamp = 2:00 for $5

        Expectation:

        live balance:
        When processing the first posting the contract (pre_posting_code())
        sees the balance of $0 and accepts the posting.
        Then when processing the second posting the contract sees the live balance
        of $1999 and rejects the second posting for insufficient funds.
        """

        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=1, hour=6, tzinfo=timezone.utc)

        events = []

        events.append(self.default_create_account_instruction(start))

        events.append(
            create_outbound_hard_settlement_instruction(
                client_batch_id="111",
                amount="1999.00",
                denomination="GBP",
                target_account_id="Main account",
                internal_account_id="1",
                client_transaction_id="test_1",
                instruction_details={"transaction_code": "1234"},
                value_timestamp=(start + timedelta(hours=3)),
                event_datetime=(start + timedelta(hours=3)),
            )
        )

        events.append(
            create_outbound_hard_settlement_instruction(
                client_batch_id="111",
                amount="5.00",
                denomination="GBP",
                target_account_id="Main account",
                internal_account_id="1",
                client_transaction_id="test_4",
                instruction_details={"transaction_code": "6011"},
                value_timestamp=(start + timedelta(hours=2)),
                event_datetime=(start + timedelta(hours=4)),
            )
        )

        res = self.run_test(start, end, events)

        self.assertIn("Posting exceeds unarranged_overdraft_limit", get_logs(res))

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "Main account": {
                    end: [
                        (BalanceDimensions(denomination="EUR"), "0"),
                        (BalanceDimensions(denomination="GBP"), "-1999"),
                        (BalanceDimensions(denomination="USD"), "0"),
                    ]
                }
            },
        )

    def test_close_code_applies_overdraft_interest_fees_and_reverts_deposit_interest(
        self,
    ):

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        deposit_to_od_date = start + timedelta(days=5, hours=2)
        od_to_deposit_date = start + timedelta(days=20, hours=2)
        end = od_to_deposit_date + timedelta(hours=1)

        sub_tests = [
            SubTest(
                description="Credit account for payable deposit interest accrual",
                events=[
                    create_inbound_hard_settlement_instruction(amount="1000", event_datetime=start)
                ],
                expected_balances_at_ts={start: {"Main account": [(DEFAULT_DIMENSIONS, "1000")]}},
            ),
            SubTest(
                description="Debit account for receivable overdraft interest accrual",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="2200", event_datetime=deposit_to_od_date
                    ),
                ],
                expected_balances_at_ts={
                    deposit_to_od_date: {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-1200"),
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0.68495"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "0.68495")],
                        INTEREST_PAID_ACCOUNT: [(DEFAULT_DIMENSIONS, "0.68495")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                        INTEREST_RECEIVED_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                    }
                },
            ),
            SubTest(
                description="Credit account for payable deposit interest accrual",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="3000", event_datetime=od_to_deposit_date
                    ),
                ],
                expected_balances_at_ts={
                    od_to_deposit_date: {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "1800"),
                            (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "-75"),
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0.68495"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-7.0182"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "0.68495")],
                        INTEREST_PAID_ACCOUNT: [(DEFAULT_DIMENSIONS, "0.68495")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "7.0182")],
                        INTEREST_RECEIVED_ACCOUNT: [(DEFAULT_DIMENSIONS, "7.0182")],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "75")],
                        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "75")],
                    }
                },
            ),
            SubTest(
                description="Close account",
                events=[update_account_status_pending_closure(end, "Main account")],
                expected_balances_at_ts={
                    end: {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "1717.98"),
                            (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "0"),
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "0"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "0.0")],
                        INTEREST_PAID_ACCOUNT: [(DEFAULT_DIMENSIONS, "0.0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                        INTEREST_RECEIVED_ACCOUNT: [(DEFAULT_DIMENSIONS, "7.02")],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [(DEFAULT_DIMENSIONS, "75")],
                        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [(DEFAULT_DIMENSIONS, "0")],
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_max_daily_deposit_in_single_posting(self):
        """Check if deposits over `maximum_daily_deposit` are rejected when deposited in 1 go."""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "1000",
            "maximum_daily_withdrawal": "1000",
        }
        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="1001", event_datetime=start + timedelta(hours=1)
            ),
            create_inbound_hard_settlement_instruction(
                amount="1000", event_datetime=start + timedelta(hours=1)
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("1000")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 1)

    def test_max_daily_deposit_multiple_postings(self):
        """Check if deposits over `maximum_daily_deposit` are rejected when deposited over multi
        postings
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)
        template_params = {**default_template_params, "maximum_daily_deposit": "1001"}
        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="500", event_datetime=start + timedelta(hours=1)
            ),
            create_inbound_hard_settlement_instruction(
                amount="700", event_datetime=start + timedelta(hours=3)
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("500")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 1)

    def test_max_daily_deposit_multiple_postings_concurrent(self):
        """Are deposits over `maximum_daily_deposit` rejected when deposited over multiple
        postings at the same time
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "1001",
        }
        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="500", event_datetime=start + timedelta(hours=3)
            ),
            create_inbound_hard_settlement_instruction(
                amount="700", event_datetime=start + timedelta(hours=3)
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("500")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 1)

    def test_max_daily_deposit_under_24_hrs(self):
        """Check if `maximum_daily_deposit` is respected over the midnight boundary"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=3, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "1001",
        }

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="1000", event_datetime=start + timedelta(hours=22)
            ),
            # This should fail as it takes us over maximum_daily_deposit
            create_inbound_hard_settlement_instruction(
                amount="1000", event_datetime=start + timedelta(hours=23)
            ),
            # This should succeed as we're in a new day
            create_inbound_hard_settlement_instruction(
                amount="900", event_datetime=start + timedelta(days=1, hours=1)
            ),
            # This should fail
            create_inbound_hard_settlement_instruction(
                amount="400", event_datetime=start + timedelta(days=1, hours=23)
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("1900")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 2)

    def test_max_daily_deposit_with_withdrawal(self):
        """Check if withdrawing modifies the `maximum_daily_deposit` limit. It should not."""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=3, hour=23, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            # Need to increase max withdrawal to withdraw enough within 1 day.
            "maximum_daily_withdrawal": "1000",
            "maximum_daily_deposit": "1001",
        }
        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="1000", event_datetime=start + timedelta(hours=1)
            ),
            # should pass because it is a new day
            create_inbound_hard_settlement_instruction(
                amount="600", event_datetime=start + timedelta(days=1, hours=2)
            ),
            # This is over the deposit limit
            create_inbound_hard_settlement_instruction(
                amount="600", event_datetime=start + timedelta(days=1, hours=3)
            ),
            # Can we reset the 'counter' with a withdrawal?
            create_outbound_hard_settlement_instruction(
                amount="600", event_datetime=start + timedelta(days=1, hours=4)
            ),
            # The next two are still over the deposit limit
            create_inbound_hard_settlement_instruction(
                amount="600", event_datetime=start + timedelta(days=1, hours=5)
            ),
            create_inbound_hard_settlement_instruction(
                amount="500", event_datetime=start + timedelta(days=1, hours=5)
            ),
            # These next two should work
            create_inbound_hard_settlement_instruction(
                amount="400", event_datetime=start + timedelta(days=1, hours=6)
            ),
            create_inbound_hard_settlement_instruction(
                amount="600", event_datetime=start + timedelta(days=2, hours=7)
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("2000")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 5)

    def test_max_daily_withdrawal_single_posting(self):
        """
        Check if `maximum_daily_withdrawal` is respected when withdrawn in one go.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "maximum_daily_withdrawal": "100",
        }

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="500", event_datetime=start + timedelta(hours=1)
            ),
            create_outbound_hard_settlement_instruction(
                amount="101", event_datetime=start + timedelta(hours=2)
            ),
            create_outbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(hours=2)
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("400")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 2)

    def test_max_daily_withdrawal(self):
        """
        Check if `maximum_daily_withdrawal` is respected with deposits inbetween, and over
        multiple days.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=3, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "maximum_daily_withdrawal": "100",
        }

        events = [
            self.default_create_account_instruction(start),
            # These 3 should work as expected
            create_inbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(hours=1)
            ),
            create_outbound_hard_settlement_instruction(
                amount="50", event_datetime=start + timedelta(hours=2)
            ),
            create_outbound_hard_settlement_instruction(
                amount="50", event_datetime=start + timedelta(hours=3)
            ),
            # This will bring the balance up to 100 again
            create_inbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(hours=4)
            ),
            # This should fail as we've already withdrawn the max daily amount
            create_outbound_hard_settlement_instruction(
                amount="60", event_datetime=start + timedelta(hours=5)
            ),
            create_inbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(hours=7)
            ),
            # The following 2 should succeed as the withdrawals are on a new day
            create_outbound_hard_settlement_instruction(
                amount="50", event_datetime=start + timedelta(days=1, hours=5)
            ),
            create_outbound_hard_settlement_instruction(
                amount="50", event_datetime=start + timedelta(days=1, hours=6)
            ),
            create_inbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(days=1, hours=7)
            ),
            # This should fail
            create_outbound_hard_settlement_instruction(
                amount="50", event_datetime=start + timedelta(days=1, hours=8)
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("200")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 8)

    def test_max_daily_withdrawal_under_24_hrs(self):
        """Check if `maximum_daily_withdrawal` is respected over the midnight boundary"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=3, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "maximum_daily_withdrawal": "100",
        }

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="1000", event_datetime=start + timedelta(hours=1)
            ),
            create_outbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(hours=22)
            ),
            # This should fail as we've already withdrawn the max daily amount
            create_outbound_hard_settlement_instruction(
                amount="60", event_datetime=start + timedelta(hours=23)
            ),
            # The following should succeed as the withdrawal is on a new day
            create_outbound_hard_settlement_instruction(
                amount="90", event_datetime=start + timedelta(days=1, hours=1)
            ),
            # This should fail
            create_outbound_hard_settlement_instruction(
                amount="90", event_datetime=start + timedelta(days=1, hours=23)
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("810")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 3)

    def test_min_deposit(self):
        """Check if `minimum_deposit` is respected"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=3, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "minimum_deposit": "100",
        }
        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(hours=1)
            ),
            # These should all fail did not consider values less than 0
            # as the endpoint will raise an error
            create_inbound_hard_settlement_instruction(
                amount="50", event_datetime=start + timedelta(hours=1)
            ),
            create_inbound_hard_settlement_instruction(
                amount="1", event_datetime=start + timedelta(hours=1)
            ),
            create_inbound_hard_settlement_instruction(
                amount="0.01", event_datetime=start + timedelta(hours=1)
            ),
            create_inbound_hard_settlement_instruction(
                amount="99", event_datetime=start + timedelta(hours=1)
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("100")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 1)

    def test_min_withdrawal(self):
        """
        Check if `minimum_withdrawal` is respected.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=4, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "minimum_withdrawal": "0.01",
        }

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(hours=1)
            ),
            create_outbound_hard_settlement_instruction(
                amount="0.01", event_datetime=start + timedelta(hours=2)
            ),
            create_outbound_hard_settlement_instruction(
                amount="0.001", event_datetime=start + timedelta(hours=3)
            ),
            create_outbound_hard_settlement_instruction(
                amount="0.009", event_datetime=start + timedelta(hours=3)
            ),
            create_outbound_hard_settlement_instruction(
                amount="0.005", event_datetime=start + timedelta(hours=3)
            ),
            create_outbound_hard_settlement_instruction(
                amount="0.00999999999999999999999999999",
                event_datetime=start + timedelta(hours=3),
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("99.99")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 2)

    def test_max_balance(self):
        """Check if deposits over `maximum_balance` are rejected"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=11, hour=23, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "maximum_balance": "10000",
        }
        instance_params = {
            **default_instance_params,
            "interest_application_day": "28",
        }
        events = [
            self.default_create_account_instruction(start, instance_params),
            # This will create 10 transactions over 10 days to build up to `maximum_balance`
            *[
                create_inbound_hard_settlement_instruction(
                    amount="1000", event_datetime=start + timedelta(days=i, hours=1)
                )
                for i in range(0, 10)
            ],
            # This should fail over max allowable balance
            create_inbound_hard_settlement_instruction(
                amount="600", event_datetime=start + timedelta(days=10, hours=1)
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("10000")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 10)

    def test_max_balance_with_interest(self):
        """
        Check that interest is applied correctly if account is over `maximum_balance`.
        Check user still cannot deposit.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=28, hour=23, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "maximum_balance": "10000",
            "deposit_tier_ranges": dumps(
                {
                    "tier1": {"min": "0"},
                    "tier2": {"min": "15000.00"},
                }
            ),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.149", "tier2": "-0.1485"}),
        }
        instance_params = {
            **default_instance_params,
            "interest_application_day": "28",
        }
        events = [
            self.default_create_account_instruction(start, instance_params),
            # This will create 10 transactions over 10 days to build up to `maximum_balance`
            *[
                create_inbound_hard_settlement_instruction(
                    amount="1000", event_datetime=start + timedelta(days=i, hours=1)
                )
                for i in range(0, 10)
            ],
            # The next 2 events shouldn't get through to the account
            create_inbound_hard_settlement_instruction(
                amount="600", event_datetime=start + timedelta(days=10, hours=1)
            ),
            create_inbound_hard_settlement_instruction(
                amount="1000", event_datetime=start + timedelta(days=14, hours=1)
            ),
        ]

        # account will still incur interest even if the event below is not added
        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("10091.85")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 11)

    def test_rejected_if_monthly_allowed_withdrawal_number_exceeded_hard_limit(self):
        start = datetime(year=2020, month=1, day=10, tzinfo=timezone.utc)
        end = datetime(year=2020, month=2, day=13, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["deposit_tier_ranges"] = dumps(
            {"tier1": {"min": "0"}, "tier2": {"min": "15000.00"}}
        )
        template_params["deposit_interest_rate_tiers"] = dumps(
            {"tier1": "0.149", "tier2": "-0.1485"}
        )
        template_params["monthly_withdrawal_limit"] = "5"
        template_params["reject_excess_withdrawals"] = "true"
        template_params["excess_withdrawal_fee"] = "10"

        instance_params = default_instance_params.copy()
        instance_params["interest_application_day"] = "5"
        events = [
            self.default_create_account_instruction(start, instance_param_vals=instance_params),
            create_inbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(hours=0)
            ),
            *[
                create_outbound_hard_settlement_instruction(
                    amount="10",
                    event_datetime=start
                    + timedelta(
                        days=i,
                    ),
                )
                for i in range(1, 6)
            ],
            # deposit should not be rejected
            create_inbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(days=6)
            ),
            create_outbound_hard_settlement_instruction(
                amount="10", event_datetime=start + timedelta(days=30)
            ),
            create_outbound_hard_settlement_instruction(
                amount="10", event_datetime=start + timedelta(days=31)
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("141.41")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 9)

        monthly_withdrawal_limit = template_params["monthly_withdrawal_limit"]
        self.assertIn(
            f"Exceeding monthly allowed withdrawal number: {monthly_withdrawal_limit}",
            get_logs(res),
        )

    def test_excess_withdrawal_fee_application(self):
        start = datetime(year=2020, month=1, day=1, hour=2, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=1, hour=10, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["monthly_withdrawal_limit"] = "1"
        template_params["reject_excess_withdrawals"] = "false"
        template_params["excess_withdrawal_fee"] = "10"

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                amount="100", event_datetime=start + timedelta(hours=0)
            ),
            create_outbound_hard_settlement_instruction(
                amount="10", event_datetime=start + timedelta(hours=2)
            ),
            create_outbound_hard_settlement_instruction(
                amount="10", event_datetime=start + timedelta(hours=3)
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, Decimal("70")),
                ]
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 4)

    def test_excess_withdrawal_limit(self):
        start = datetime(year=2020, month=1, day=10, tzinfo=timezone.utc)
        end = datetime(year=2020, month=2, day=13, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["reject_excess_withdrawals"] = "true"
        template_params["excess_withdrawal_fee"] = "10"
        template_params["deposit_tier_ranges"] = dumps(
            {"tier1": {"min": "0"}, "tier2": {"min": "15000.00"}}
        )
        template_params["deposit_interest_rate_tiers"] = dumps(
            {"tier1": "0.149", "tier2": "-0.1485"}
        )
        template_params["monthly_withdrawal_limit"] = "3"
        denomination = default_template_params["denomination"]
        instance_params = default_instance_params.copy()
        instance_params["interest_application_day"] = "5"

        withdrawal_instruction = OutboundHardSettlement(
            target_account_id="Main account",
            amount="10",
            denomination=denomination,
        )

        deposit_instruction = InboundHardSettlement(
            target_account_id="Main account",
            amount="100",
            denomination=denomination,
        )

        sub_tests = [
            SubTest(
                description="Fund the account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500.00",
                        denomination=denomination,
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=start,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        "Main account": [
                            (BalanceDimensions(denomination=denomination), "500.00"),
                        ],
                    }
                },
            ),
            SubTest(
                description="PIB with 3 withdrawals at limit is accepted and notification is sent",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            withdrawal_instruction,
                            withdrawal_instruction,
                            withdrawal_instruction,
                        ],
                        event_datetime=start + timedelta(days=1),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=1): {
                        "Main account": [
                            (BalanceDimensions(denomination=denomination), "470.00"),
                        ],
                        EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination=denomination), "0.00")
                        ],
                    }
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="CASA_TRANSACTION_LIMIT_WARNING",
                        account_id="Main account",
                        run_times=[start + timedelta(days=1)],
                        contexts=[
                            {
                                "account_id": "Main account",
                                "limit_type": "Monthly Withdrawal Limit",
                                "limit": "3",
                                "value": "3",
                                "message": "Warning: Reached monthly withdrawal transaction limit, "
                                "no further withdrawals will be allowed for the current period.",
                            }
                        ],
                    )
                ],
            ),
            SubTest(
                description="Limit increased and excess withdrawals allowed, so PIB with "
                "3 withdrawals (6 total, 1 excess) results in fee",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=1, hours=6),
                        smart_contract_version_id=CASA_CONTRACT_VERSION_ID,
                        monthly_withdrawal_limit="5",
                    ),
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=1, hours=7),
                        smart_contract_version_id=CASA_CONTRACT_VERSION_ID,
                        reject_excess_withdrawals="false",
                    ),
                    create_posting_instruction_batch(
                        instructions=[
                            withdrawal_instruction,
                            withdrawal_instruction,
                            withdrawal_instruction,
                        ],
                        event_datetime=start + timedelta(days=2),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=2): {
                        "Main account": [
                            (BalanceDimensions(denomination=denomination), "430.00"),
                        ],
                        EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination=denomination), "10.00")
                        ],
                    }
                },
                expected_workflows=[
                    ExpectedWorkflow(
                        workflow_definition_id="CASA_TRANSACTION_LIMIT_WARNING",
                        account_id="Main account",
                        run_times=[start + timedelta(days=2)],
                        contexts=[
                            {
                                "account_id": "Main account",
                                "limit_type": "Monthly Withdrawal Limit",
                                "limit": "5",
                                "value": "6",
                                "message": "Warning: Reached monthly withdrawal transaction limit, "
                                "charges will be applied for the next withdrawal.",
                            }
                        ],
                    )
                ],
            ),
            SubTest(
                description="Set fees to 0 and make another excess withdrawal",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=2, hours=6),
                        smart_contract_version_id=CASA_CONTRACT_VERSION_ID,
                        excess_withdrawal_fee="0",
                    ),
                    # exceeds withdrawal limit with fee 0
                    create_outbound_hard_settlement_instruction(
                        amount="10", event_datetime=start + timedelta(days=3)
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=3): {
                        "Main account": [
                            (BalanceDimensions(denomination=denomination), "420.00"),
                        ],
                        EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination=denomination), "10.00")
                        ],
                    }
                },
            ),
            SubTest(
                description="Set excess withdrawals to be rejected and make another withdrawal",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=3, hours=6),
                        smart_contract_version_id=CASA_CONTRACT_VERSION_ID,
                        reject_excess_withdrawals="true",
                    ),
                    # exceeds withdrawal hard limit, entire pib rejected
                    create_posting_instruction_batch(
                        [withdrawal_instruction, deposit_instruction],
                        start + timedelta(days=4),
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(days=4),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Exceeding monthly allowed withdrawal number: 5",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=4): {
                        "Main account": [
                            (BalanceDimensions(denomination=denomination), "420.00"),
                        ],
                        EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination=denomination), "10.00")
                        ],
                    }
                },
            ),
            SubTest(
                description="Check deposits are still accepted",
                events=[
                    create_posting_instruction_batch(
                        [deposit_instruction],
                        start + timedelta(days=5),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=5): {
                        "Main account": [
                            (BalanceDimensions(denomination=denomination), "520.00"),
                        ],
                        EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination=denomination), "10.00")
                        ],
                    }
                },
            ),
            SubTest(
                description="Re-enable fees and rejections",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=5, hours=6),
                        smart_contract_version_id=CASA_CONTRACT_VERSION_ID,
                        excess_withdrawal_fee="15",
                    ),
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=5, hours=7),
                        smart_contract_version_id=CASA_CONTRACT_VERSION_ID,
                        reject_excess_withdrawals="false",
                    ),
                ],
            ),
            SubTest(
                description="Fees are only charged for withdrawals and not deposits",
                events=[
                    create_posting_instruction_batch(
                        [withdrawal_instruction, deposit_instruction],
                        start + timedelta(days=6),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=6): {
                        "Main account": [
                            (BalanceDimensions(denomination=denomination), "595.00"),
                        ],
                        EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination=denomination), "25.00")
                        ],
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_change_date(self):
        """Test that changing interest application day works as expected"""
        start = datetime(year=2019, month=1, day=27, tzinfo=timezone.utc)
        end = datetime(year=2019, month=2, day=4, tzinfo=timezone.utc)
        instance_params = {
            **default_instance_params,
            "interest_application_day": "27",
        }
        template_params = {
            **default_template_params,
            "deposit_interest_rate_tiers": dumps({"tier1": "0.149", "tier2": "-0.1485"}),
            "deposit_tier_ranges": dumps(
                {
                    "tier1": {"min": "0"},
                    "tier2": {"min": "15000.00"},
                }
            ),
        }

        events = [
            self.default_create_account_instruction(start, instance_params),
            create_instance_parameter_change_event(
                timestamp=start, account_id="Main account", interest_application_day="3"
            ),
            create_inbound_hard_settlement_instruction(
                amount="100",
                event_datetime=start + timedelta(hours=1),
                target_account_id="Main account",
                denomination=default_template_params["denomination"],
            ),
        ]

        res = self.run_test(start, end, events, template_params)
        actual_balances = get_balances(res)
        expected_balances = {
            "Main account": {
                end: [
                    (DEFAULT_DIMENSIONS, "100.29"),
                ],
            }
        }

        self.check_balances(expected_balances, actual_balances)
        self.assertEqual(get_num_postings(res, account_id="Main account"), 2)

    def test_schedules_interest_payment_day_change(self):
        """
        Test that the interest application schedule is updated
        when the interest application day parameter is changed
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=2, tzinfo=timezone.utc)
        instance_params = {
            **default_instance_params,
            "interest_application_day": "1",
        }
        template_params = {
            **default_template_params,
            "interest_application_hour": "0",
            "interest_application_minute": "1",
            "interest_application_second": "0",
            "deposit_interest_application_frequency": "monthly",
            "interest_accrual_hour": "0",
            "interest_accrual_minute": "0",
            "interest_accrual_second": "0",
        }
        new_interest_application_day = "3"
        events = [
            self.default_create_account_instruction(start, instance_params),
            create_instance_parameter_change_event(
                timestamp=start,
                account_id="Main account",
                interest_application_day=new_interest_application_day,
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        accrue_interest_event = get_processed_scheduled_events(
            res, event_id="ACCRUE_INTEREST_AND_DAILY_FEES", account_id="Main account"
        )

        # 367 because we added 2 days
        self.assertEqual(len(accrue_interest_event), 367)
        expected_date = start
        for i in range(0, len(accrue_interest_event)):
            date = datetime.fromisoformat(accrue_interest_event[i][:-1])
            self.assertEqual(date.day, expected_date.day)
            self.assertEqual(date.year, expected_date.year)
            self.assertEqual(date.month, expected_date.month)
            self.assertEqual(date.hour, int(template_params["interest_accrual_hour"]))
            self.assertEqual(date.minute, int(template_params["interest_accrual_minute"]))
            self.assertEqual(date.second, int(template_params["interest_accrual_second"]))
            expected_date = expected_date + relativedelta(days=1)

        apply_accrued_interest_event = get_processed_scheduled_events(
            res, event_id="APPLY_ACCRUED_INTEREST", account_id="Main account"
        )
        # this is monthly interest so should be 12
        self.assertEqual(len(apply_accrued_interest_event), 12)
        expected_date = start
        for i in range(0, len(apply_accrued_interest_event)):
            date = datetime.fromisoformat(apply_accrued_interest_event[i][:-1])
            self.assertEqual(date.day, int(new_interest_application_day))
            self.assertEqual(date.year, expected_date.year)
            self.assertEqual(date.month, expected_date.month)
            self.assertEqual(date.hour, int(template_params["interest_application_hour"]))
            self.assertEqual(date.minute, int(template_params["interest_application_minute"]))
            self.assertEqual(date.second, int(template_params["interest_application_second"]))
            # interest only starts in 3rd day so interest starts on 2nd month
            expected_date = expected_date + relativedelta(months=1)

    def test_interest_application_frequency_quarterly_remains_unchanged(self):
        """
        Test that setting a quarterly interest application frequency works as expected.
        """
        start = datetime(year=2019, month=1, day=27, tzinfo=timezone.utc)
        end = datetime(year=2020, month=2, day=4, tzinfo=timezone.utc)
        template_params = {
            **default_template_params,
            "deposit_interest_application_frequency": "quarterly",
            "interest_application_hour": "0",
            "interest_application_minute": "1",
            "interest_application_second": "0",
        }
        instance_params = {
            **default_instance_params,
            "interest_application_day": "28",
        }

        # check that quarterly value is kept by the scheduler, even though
        # the frequency parameter has changed
        events = [
            self.default_create_account_instruction(start, instance_params),
            create_template_parameter_change_event(
                timestamp=datetime(year=2019, month=6, day=2, tzinfo=timezone.utc),
                smart_contract_version_id=CASA_CONTRACT_VERSION_ID,
                deposit_interest_application_frequency="annually",
            ),
        ]

        res = self.run_test(start, end, events, template_params)

        apply_accrued_interest_event = get_processed_scheduled_events(
            res, event_id="APPLY_ACCRUED_INTEREST", account_id="Main account"
        )

        # quarterly so should be 4
        self.assertEqual(len(apply_accrued_interest_event), 4)

        expected_date = start
        for i in range(0, len(apply_accrued_interest_event)):
            # only 3 since it includes current month
            expected_date = expected_date + relativedelta(months=3)
            date = datetime.fromisoformat(apply_accrued_interest_event[i][:-1])
            self.assertEqual(date.day, int(instance_params["interest_application_day"]))
            self.assertEqual(date.year, expected_date.year)
            self.assertEqual(date.month, expected_date.month)
            self.assertEqual(date.hour, int(template_params["interest_application_hour"]))
            self.assertEqual(date.minute, int(template_params["interest_application_minute"]))
            self.assertEqual(date.second, int(template_params["interest_application_second"]))

    def test_get_derived_params(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=12, tzinfo=timezone.utc)

        instance_params = default_instance_params.copy()
        template_params = default_template_params.copy()

        sub_tests = [
            SubTest(
                description="Get account tier derived param",
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        start, "Main account", "account_tier", "CASA_TIER_LOWER"
                    )
                ],
            ),
            SubTest(
                description="Get account tier derived param with flag event",
                events=[
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id="CASA_TIER_MIDDLE"
                    ),
                    create_flag_event(
                        timestamp=start + relativedelta(hours=6),
                        expiry_timestamp=end,
                        flag_definition_id="CASA_TIER_MIDDLE",
                        account_id="Main account",
                    ),
                ],
                expected_derived_parameters=[
                    ExpectedDerivedParameter(
                        start + relativedelta(hours=6),
                        "Main account",
                        "account_tier",
                        "CASA_TIER_MIDDLE",
                    )
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_interest_and_fees_handled_on_closure(self):
        """
        Check that residual accrued deposit interest is reversed, overdraft interest is applied,
        and fees are applied.
        Note: It's not possible to accrue deposit and overdraft interest at the same time, but
        separate accruals can result in residual amounts for both
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=3, hour=6, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Accrue some overdraft interest and fees",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "1500", start + relativedelta(hours=6)
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=1): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "-1500"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-0.58993"),
                            (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "-5"),
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Accrue some deposit interest",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "2500", start + relativedelta(days=1, hours=6)
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + relativedelta(days=2): {
                        "Main account": [
                            (DEFAULT_DIMENSIONS, "1000"),
                            (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "-5"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "-0.58993"),
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0.13699"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Ensure close_code reverses deposit and applies overdraft interest",
                events=[
                    update_account_status_pending_closure(timestamp=end, account_id="Main account")
                ],
                expected_balances_at_ts={
                    end: {
                        "Main account": [
                            # -0.58993 is rounded to -0.59
                            (DEFAULT_DIMENSIONS, "994.41"),
                            (ACCRUED_OVERDRAFT_FEE_RECEIVABLE_DIMENSIONS, "0"),
                            (ACCRUED_OVERDRAFT_RECEIVABLE_DIMENSIONS, "0"),
                            (ACCRUED_DEPOSIT_PAYABLE_DIMENSIONS, "0"),
                        ]
                    },
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
        unittest.main(CASATest)
    else:
        unittest.main(CASATest())
