# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
import calendar
import sys
import unittest
from ctypes import ArgumentError
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta as timedelta
from json import dumps

# library
from library.us_products_v3.constants.files import US_CHECKING_TEMPLATE

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractModuleConfig,
    ExpectedRejection,
    ExpectedSchedule,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_auth_adjustment_instruction,
    create_custom_instruction,
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
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase
from inception_sdk.vault.postings.posting_classes import (
    InboundHardSettlement,
    OutboundHardSettlement,
)

CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "interest": "library/common/contract_modules/interest.py",
}
ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"
DEFAULT_DENOMINATION = "USD"
DORMANCY_FLAG = "ACCOUNT_DORMANT"
STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG = "STANDARD_OVERDRAFT_TRANSACTION_COVERAGE"

ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
OVERDRAFT_FEE_INCOME_ACCOUNT = "OVERDRAFT_FEE_INCOME"
MAINTENANCE_FEE_INCOME_ACCOUNT = "MAINTENANCE_FEE_INCOME"
OVERDRAFT_FEE_RECEIVABLE_ACCOUNT = "OVERDRAFT_FEE_RECEIVABLE"
MINIMUM_BALANCE_FEE_INCOME_ACCOUNT = "MINIMUM_BALANCE_FEE_INCOME"
INACTIVITY_FEE_INCOME_ACCOUNT = "INACTIVITY_FEE_INCOME"
PROMOTIONAL_MAINTENANCE_FEE = "PROMOTIONAL_MAINTENANCE_FEE"

default_template_params = {
    "denomination": "USD",
    "additional_denominations": dumps(["GBP", "EUR"]),
    "tier_names": dumps(
        [
            "US_CHECKING_ACCOUNT_TIER_UPPER",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE",
            "US_CHECKING_ACCOUNT_TIER_LOWER",
        ]
    ),
    "deposit_interest_application_frequency": "monthly",
    "interest_accrual_days_in_year": "365",
    "standard_overdraft_per_transaction_fee": "0",
    "standard_overdraft_daily_fee": "5",
    "standard_overdraft_fee_cap": "80",
    "savings_sweep_fee": "0",
    "savings_sweep_fee_cap": "-1",
    "savings_sweep_transfer_unit": "0",
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
    "inactivity_fee_income_account": INACTIVITY_FEE_INCOME_ACCOUNT,
    "maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "0"}),
    "promotional_maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "0"}),
    "minimum_balance_threshold": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "1500"}),
    "minimum_combined_balance_threshold": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "5000"}),
    "minimum_deposit_threshold": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "500"}),
    "minimum_balance_fee": "0",
    "account_inactivity_fee": "55",
    "fees_application_day": "1",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "maximum_daily_atm_withdrawal_limit": dumps(
        {
            "US_CHECKING_ACCOUNT_TIER_UPPER": "5000",
            "US_CHECKING_ACCOUNT_TIER_MIDDLE": "2000",
            "US_CHECKING_ACCOUNT_TIER_LOWER": "1000",
        }
    ),
    "transaction_code_to_type_map": dumps({"6011": "ATM withdrawal", "3123": "eCommerce"}),
    "transaction_types": dumps(["purchase", "ATM withdrawal", "transfer"]),
    "deposit_tier_ranges": dumps(
        {
            "tier1": {"min": "0", "max": "3000.00"},
            "tier2": {"min": "3000.00", "max": "5000.00"},
            "tier3": {"min": "5000.00"},
        }
    ),
    "deposit_interest_rate_tiers": dumps({"tier1": "0.05", "tier2": "0", "tier3": "-0.035"}),
    "autosave_rounding_amount": "1.00",
    "optional_standard_overdraft_coverage": dumps(["ATM withdrawal", "eCommerce"]),
    "overdraft_protection_sweep_hour": "0",
    "overdraft_protection_sweep_minute": "0",
    "overdraft_protection_sweep_second": "0",
}

default_instance_params = {
    "fee_free_overdraft_limit": "1000",
    "standard_overdraft_limit": "2000",
    "interest_application_day": "1",
    "daily_atm_withdrawal_limit": "1000",
}


class USCheckingAccountTest(SimulationTestCase):

    contract_filepaths = [US_CHECKING_TEMPLATE]
    contract_modules = [
        ContractModuleConfig(alias, file_path)
        for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
    ]

    internal_accounts = {
        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: "ASSET",
        INTEREST_RECEIVED_ACCOUNT: "LIABILITY",
        ACCRUED_INTEREST_PAYABLE_ACCOUNT: "LIABILITY",
        INTEREST_PAID_ACCOUNT: "ASSET",
        OVERDRAFT_FEE_INCOME_ACCOUNT: "LIABILITY",
        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: "ASSET",
        MAINTENANCE_FEE_INCOME_ACCOUNT: "LIABILITY",
        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: "LIABILITY",
        INACTIVITY_FEE_INCOME_ACCOUNT: "LIABILITY",
        # This is a generic account used for external postings
        "1": "LIABILITY",
    }

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
            contract_content=self.smart_contract_path_to_content[US_CHECKING_TEMPLATE],
            template_params=template_params or default_template_params,
            account_configs=[
                AccountConfig(instance_params=instance_params or default_instance_params)
            ],
            linked_contract_modules=self.contract_modules,
        )
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=internal_accounts or self.internal_accounts,
        )

    def _create_list_of_schedule_datetimes(
        self, start: datetime, end: datetime, frequency: str
    ) -> list[datetime]:
        current_date = start
        date_list = []
        while current_date < end:
            date_list.append(current_date)
            if frequency == "daily":
                current_date = current_date + timedelta(days=1)
            elif frequency == "monthly":
                current_date = current_date + timedelta(months=1)
            elif frequency == "quarterly":
                current_date = current_date + timedelta(months=3)
            elif frequency == "yearly":
                current_date = current_date + timedelta(years=1)
            else:
                raise ArgumentError(f"{frequency} is not a supported time frequency")

        return date_list

    def test_deposit_interest_accrual_and_application(self):
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=3, day=2, tzinfo=timezone.utc)

        before_1st_interest_application = datetime(year=2020, month=2, day=1, tzinfo=timezone.utc)
        after_1st_interest_application = before_1st_interest_application + timedelta(minutes=2)

        before_2nd_interest_application = datetime(year=2020, month=3, day=1, tzinfo=timezone.utc)
        after_2nd_interest_application = before_2nd_interest_application + timedelta(minutes=2)

        sub_tests = [
            SubTest(
                description="test balance update after a single deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "283.45", start + timedelta(hours=1), denomination="USD"
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=1): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "283.45")]
                    }
                },
            ),
            SubTest(
                description="test balance update after multiple deposits",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100.00", start + timedelta(hours=2), denomination="USD"
                    ),
                    create_inbound_hard_settlement_instruction(
                        "1222.00", start + timedelta(hours=3), denomination="USD"
                    ),
                    create_inbound_hard_settlement_instruction(
                        "4768.45", start + timedelta(hours=4), denomination="USD"
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=5): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "6373.90")]
                    }
                },
            ),
            SubTest(
                description="tiered deposit interest with positive, zero and negative rates",
                expected_balances_at_ts={
                    start
                    + timedelta(days=1, hours=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "6373.90"),
                            # balance tier1 interest = 3000 * 0.05 / 365 = 0.41096
                            # balance tier2 interest = 2000 * 0 = 0
                            # balance tier3 interest = 1373.90 * -0.035 / 365 = -0.13174
                            # total receivable interest = 0.13174
                            # total payable interest = 0.41096
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_PAYABLE",
                                    denomination="USD",
                                ),
                                "0.41096",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "-0.13174",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "0",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-0.41096")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-0.13174")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    }
                },
            ),
            SubTest(
                description="accrual is correct upon change in tiered interest rates",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=1, hours=2),
                        deposit_interest_rate_tiers=dumps(
                            {"tier1": "-0.02", "tier2": "0.01", "tier3": "0.04"}
                        ),
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=2, hours=2): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "6373.90"),
                            # balance tier1 interest = 3000 * -0.02 / 365 = -0.16438
                            # balance tier2 interest = 2000 * 0.01 / 365 = 0.05479
                            # balance tier3 interest = 1373.90 * 0.04 / 365 = 0.15056
                            # total receivable interest = 0.13174 + 0.16438 = 0.29612
                            # total payable interest = 0.41096 + 0.05479 + 0.15056 = 0.61631
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_PAYABLE",
                                    denomination="USD",
                                ),
                                "0.61631",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "-0.29612",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "0",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-0.61631")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-0.29612")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    }
                },
            ),
            SubTest(
                description="accrual with actual interest_accrual_days_in_year",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=2, hours=3),
                        interest_accrual_days_in_year="actual",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=3, hours=2): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "6373.90"),
                            # 2020 is a leap year with 366 days
                            # balance tier1 interest = 3000 * -0.02 / 366 = -0.16393
                            # balance tier2 interest = 2000 * 0.01 / 366 = 0.05464
                            # balance tier3 interest = 1373.90 * 0.04 / 366 = 0.15015
                            # total receivable interest = 0.29612 + 0.16393 = 0.46005
                            # total payable interest = 0.61631 + 0.05464 + 0.15015 = 0.82110
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_PAYABLE",
                                    denomination="USD",
                                ),
                                "0.82110",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "-0.46005",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "0",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-0.82110")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-0.46005")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    }
                },
            ),
            SubTest(
                description="accrual with 360 interest_accrual_days_in_year",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=3, hours=3),
                        interest_accrual_days_in_year="360",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=4, hours=2): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "6373.90"),
                            # 2020 is a leap year with 366 days
                            # balance tier1 interest = 3000 * -0.02 / 360 = -0.16667
                            # balance tier2 interest = 2000 * 0.01 / 360 = 0.05556
                            # balance tier3 interest = 1373.90 * 0.04 / 360 = 0.15266
                            # total receivable interest = 0.46005 + 0.16667 = 0.62672
                            # total payable interest = 0.82110 + 0.05556 + 0.15266 = 1.02932
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_PAYABLE",
                                    denomination="USD",
                                ),
                                "1.02932",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "-0.62672",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "0",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-1.02932")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-0.62672")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    }
                },
            ),
            SubTest(
                description="positive interest application",
                expected_balances_at_ts={
                    before_1st_interest_application: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "6373.90"),
                            # total receivable interest = 0.62672 + (31-4)*0.16667 = 5.12681
                            # total payable interest = 1.02932 +
                            # (31-4)*(0.015266 + 0.15266) = 6.65126
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_PAYABLE",
                                    denomination="USD",
                                ),
                                "6.65126",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "-5.12681",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "0",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-6.65126")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-5.12681")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    },
                    after_1st_interest_application: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "6375.42"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_PAYABLE",
                                    denomination="USD",
                                ),
                                "0.00",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "0.00",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "0.00",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "6.65")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "5.13")
                        ],
                    },
                },
            ),
            SubTest(
                description="negative interest application",
                events=[
                    create_template_parameter_change_event(
                        timestamp=after_1st_interest_application + timedelta(hours=2),
                        deposit_interest_rate_tiers=dumps(
                            {"tier1": "-0.02", "tier2": "-0.01", "tier3": "-0.04"}
                        ),
                    )
                ],
                expected_balances_at_ts={
                    before_2nd_interest_application: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "6375.42"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "-10.87645",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "6.65")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-10.87645")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "5.13")
                        ],
                    },
                    after_2nd_interest_application: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "6364.54"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_PAYABLE",
                                    denomination="USD",
                                ),
                                "-0.00",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "0.00",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "6.65")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "16.01")
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

    def test_withdrawal_limits(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = start + timedelta(days=1, hours=8)

        sub_tests = [
            SubTest(
                description="deposits are not affected by limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "1500.00", start + timedelta(hours=1), denomination="USD"
                    ),
                    # withdrawal that reaches limit
                    create_outbound_hard_settlement_instruction(
                        "1000.00",
                        start + timedelta(hours=2),
                        denomination="USD",
                        instruction_details={"transaction_code": "6011"},
                    ),
                    create_inbound_hard_settlement_instruction(
                        "100.00", start + timedelta(hours=3), denomination="USD"
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=3, minutes=1): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "600.00")]
                    }
                },
            ),
            SubTest(
                description="atm withdrawal exceeding the limit is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "5.00",
                        start + timedelta(hours=4),
                        denomination="USD",
                        instruction_details={"transaction_code": "6011"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=4, minutes=1): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "600.00")]
                    }
                },
            ),
            SubTest(
                description="non-atm withdrawal can still go through",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "50.00",
                        start + timedelta(hours=5),
                        denomination="USD",
                        instruction_details={"transaction_code": "1234"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=5, minutes=1): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "550.00")]
                    }
                },
            ),
            SubTest(
                description="non-atm withdrawal exceeding loc limit is rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "2551.00",
                        start + timedelta(hours=5, minutes=30),
                        denomination="USD",
                        instruction_details={"transaction_code": "1234"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=5, minutes=31): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "550.00")]
                    }
                },
            ),
            SubTest(
                description="additional currencies not affected by limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "2000.00", start + timedelta(hours=6), denomination="EUR"
                    ),
                    create_outbound_hard_settlement_instruction(
                        "1500.00",
                        start + timedelta(hours=7),
                        denomination="EUR",
                        instruction_details={"transaction_code": "6011"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=7, minutes=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "550.00"),
                            (BalanceDimensions(denomination="EUR"), "500.00"),
                        ]
                    }
                },
            ),
            SubTest(
                description="atm withdrawal limit resets at midnight",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "200.00",
                        start + timedelta(days=1, microseconds=1),
                        denomination="USD",
                        instruction_details={"transaction_code": "6011"},
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=1, minutes=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "350.00"),
                            (BalanceDimensions(denomination="EUR"), "500.00"),
                        ]
                    }
                },
            ),
            SubTest(
                description="entire pib is rejected if one of the pis exceeds limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "2000.00",
                        start + timedelta(days=1, hours=1),
                        denomination="USD",
                    ),
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                "2000",
                                target_account_id="Main account",
                                denomination="USD",
                            ),
                            InboundHardSettlement(
                                "3000",
                                target_account_id="Main account",
                                denomination="USD",
                            ),
                        ],
                        instruction_details={"transaction_code": "6011"},
                        event_datetime=start + timedelta(days=1, hours=2),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(days=1, hours=2, minutes=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "2350.00"),
                            (BalanceDimensions(denomination="EUR"), "500.00"),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests
        )

        self.run_test_scenario(test_scenario)

    def test_overdraft_interest_accrual_application_and_fees(self):
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=4, day=2, hour=1, tzinfo=timezone.utc)

        before_1st_monthly_fee = datetime(year=2020, month=2, day=1, tzinfo=timezone.utc)
        after_1st_monthly_fee = before_1st_monthly_fee + timedelta(minutes=2)

        before_2nd_monthly_fee = datetime(year=2020, month=3, day=1, tzinfo=timezone.utc)
        after_2nd_monthly_fee = before_2nd_monthly_fee + timedelta(minutes=2)

        sub_tests = [
            SubTest(
                description="Spend from the account",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "450", start + timedelta(hours=1), denomination="USD"
                    )
                ],
                expected_balances_at_ts={
                    before_1st_monthly_fee: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-450.00")],
                    },
                    after_1st_monthly_fee: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-450")],
                    },
                },
            ),
            SubTest(
                description="daily standard overdraft fees are incurred",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "1500.00",
                        after_1st_monthly_fee + timedelta(hours=1),
                        denomination="USD",
                    )
                ],
                expected_balances_at_ts={
                    after_1st_monthly_fee
                    + timedelta(days=1, hours=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "-1950"),
                            # 2020 is a leap year but note that 'interest_accrual_days_in_year'
                            # is set to 365
                            # total accrued overdraft fee = 5
                            (
                                BalanceDimensions(
                                    address="ACCRUED_OVERDRAFT_FEE_RECEIVABLE", denomination="USD"
                                ),
                                "-5",
                            ),
                        ],
                        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-5")
                        ],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0"),
                        ],
                    },
                    after_1st_monthly_fee
                    + timedelta(days=7, hours=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "-1950"),
                            # total accrued overdraft fee = 5 * 7 = 35
                            (
                                BalanceDimensions(
                                    address="ACCRUED_OVERDRAFT_FEE_RECEIVABLE", denomination="USD"
                                ),
                                "-35",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-35"),
                        ],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0"),
                        ],
                    },
                },
            ),
            SubTest(
                description="daily overdraft fee cap and application",
                expected_balances_at_ts={
                    # overdraft fees capped at 80
                    before_2nd_monthly_fee: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "-1950"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_OVERDRAFT_FEE_RECEIVABLE", denomination="USD"
                                ),
                                "-80",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        OVERDRAFT_FEE_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-80"),
                        ],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0"),
                        ],
                    },
                    # This test also covers fee accrual bringing total balance
                    # beyond the product's overdraft limit
                    # i.e. in this case the overdraft cap is -2000
                    # and the expected Main account balance is -2057.74
                    after_2nd_monthly_fee: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "-2030"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests
        )

        self.run_test_scenario(test_scenario)

    def test_maintenance_fees(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=9, day=1, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}),
            "promotional_maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "5"}),
            "fees_application_day": "31",
            "fees_application_hour": "17",
            "fees_application_minute": "30",
            "fees_application_second": "30",
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
        }

        def _get_last_day_of_month_fee_application(year, month):
            last_day_of_month = calendar.monthrange(year, month)[1]
            before_fee_application = datetime(
                year=year,
                month=month,
                day=last_day_of_month,
                hour=17,
                minute=30,
                second=29,
                tzinfo=timezone.utc,
            )
            after_fee_application = before_fee_application + timedelta(seconds=2)
            return before_fee_application, after_fee_application

        (
            before_1st_application_day,
            after_1st_application_day,
        ) = _get_last_day_of_month_fee_application(2021, 1)
        (
            before_fee_application_feb,
            after_fee_application_feb,
        ) = _get_last_day_of_month_fee_application(2021, 2)
        (
            before_fee_application_mar,
            after_fee_application_mar,
        ) = _get_last_day_of_month_fee_application(2021, 3)
        (
            before_fee_application_apr,
            after_fee_application_apr,
        ) = _get_last_day_of_month_fee_application(2021, 4)
        (
            before_fee_application_may,
            after_fee_application_may,
        ) = _get_last_day_of_month_fee_application(2021, 5)
        (
            before_fee_application_jun,
            after_fee_application_jun,
        ) = _get_last_day_of_month_fee_application(2021, 6)
        (
            before_fee_application_jul,
            after_fee_application_jul,
        ) = _get_last_day_of_month_fee_application(2021, 7)
        (
            before_fee_application_aug,
            after_fee_application_aug,
        ) = _get_last_day_of_month_fee_application(2021, 8)

        sub_tests = [
            SubTest(
                description="monthly maintenance fee does not apply within 1 month of creation",
                events=[
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=PROMOTIONAL_MAINTENANCE_FEE
                    ),
                    create_inbound_hard_settlement_instruction("400.00", start, denomination="USD"),
                ],
                expected_balances_at_ts={
                    before_1st_application_day: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "400.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                    },
                    after_1st_application_day: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "400.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                    },
                },
            ),
            SubTest(
                description="monthly maintenance fee application on last day of feb",
                expected_balances_at_ts={
                    before_fee_application_feb: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "400.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                    },
                    after_fee_application_feb: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "390.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "10.00"),
                        ],
                    },
                },
            ),
            SubTest(
                description="promotional fee applied last day of mar",
                events=[
                    create_flag_event(
                        timestamp=after_fee_application_feb,
                        expiry_timestamp=after_fee_application_mar,
                        flag_definition_id=PROMOTIONAL_MAINTENANCE_FEE,
                        account_id="Main account",
                    )
                ],
                expected_balances_at_ts={
                    before_fee_application_mar: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "390.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "10.00"),
                        ],
                    },
                    after_fee_application_mar: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "385.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "15.00"),
                        ],
                    },
                },
            ),
            SubTest(
                description="maintenance fee waived if minimum deposit is met",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "500.00",
                        after_fee_application_mar + timedelta(hours=1),
                        denomination="USD",
                    )
                ],
                expected_balances_at_ts={
                    before_fee_application_apr: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "885.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "15.00"),
                        ],
                    },
                    after_fee_application_apr: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "885.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "15.00"),
                        ],
                    },
                },
            ),
            SubTest(
                description="maintenance fee start to incur again while no minimum deposit",
                expected_balances_at_ts={
                    before_fee_application_may: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "885.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "15.00"),
                        ],
                    },
                    after_fee_application_may: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "875.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "25.00"),
                        ],
                    },
                },
            ),
            SubTest(
                description="maintenance fee incurred if minimum_balance_threshold not met",
                events=[
                    # increase deposit threshold to single out minimum balance threshold criterion
                    create_template_parameter_change_event(
                        timestamp=after_fee_application_may + timedelta(minutes=1),
                        minimum_deposit_threshold=dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "2000"}),
                    ),
                    # as the balance sampling time is at midnight, the balance average will be
                    # just below 1500 threshold next month
                    create_inbound_hard_settlement_instruction(
                        "635.00",
                        after_fee_application_may + timedelta(minutes=1),
                        denomination="USD",
                    ),
                ],
                expected_balances_at_ts={
                    before_fee_application_jun: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1510.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "25.00"),
                        ],
                    },
                    after_fee_application_jun: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1500.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "35.00"),
                        ],
                    },
                },
            ),
            SubTest(
                description="maintenance fee waived if minimum_balance_threshold met",
                expected_balances_at_ts={
                    before_fee_application_jul: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1500.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "35.00"),
                        ],
                    },
                    after_fee_application_jul: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1500.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "35.00"),
                        ],
                    },
                },
            ),
            SubTest(
                description="maintenance fee reapplies while minimum_balance_threshold not met",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "100.00",
                        before_fee_application_aug + timedelta(days=-2),
                        denomination="USD",
                    )
                ],
                expected_balances_at_ts={
                    before_fee_application_aug: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1400.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "35.00"),
                        ],
                    },
                    after_fee_application_aug: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1390.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "45.00"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_minimum_balance_fee(self):
        """
        Mean balance below threshold in sampling period and so fee charged.
        Above threshold before and after to check period.
        Sampling time at midnight
        """
        start = datetime(year=2020, month=12, day=1, hour=15, tzinfo=timezone.utc)
        end = datetime(year=2021, month=4, day=2, tzinfo=timezone.utc)

        after_1st_fee_sampling_time = datetime(
            year=2021, month=1, day=31, hour=23, tzinfo=timezone.utc
        )
        after_1st_fees_application = datetime(
            year=2021, month=2, day=1, hour=16, tzinfo=timezone.utc
        )
        before_2nd_fees_application = datetime(
            year=2021, month=2, day=28, hour=23, tzinfo=timezone.utc
        )
        after_2nd_fees_application = datetime(
            year=2021, month=3, day=1, hour=1, tzinfo=timezone.utc
        )

        template_params = {
            **default_template_params,
            "minimum_balance_fee": "100",
            "tier_names": dumps(["X", "Y", "Z"]),
            "minimum_balance_threshold": dumps({"X": "100", "Y": "300", "Z": "500"}),
            "maintenance_fee_monthly": dumps({"X": "0", "Y": "0", "Z": "0"}),
            "minimum_combined_balance_threshold": dumps({"X": "5000", "Y": "5000", "Z": "5000"}),
            "minimum_deposit_threshold": dumps({"X": "500", "Y": "500", "Z": "500"}),
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
        }

        sub_tests = [
            SubTest(
                description="no fee charge when mean balance at the correct tiered threshold",
                events=[
                    create_flag_definition_event(timestamp=start, flag_definition_id="X"),
                    create_flag_definition_event(timestamp=start, flag_definition_id="Y"),
                    create_flag_definition_event(timestamp=start, flag_definition_id="Z"),
                    create_flag_event(
                        timestamp=start,
                        expiry_timestamp=end,
                        flag_definition_id="X",
                        account_id="Main account",
                    ),
                    create_inbound_hard_settlement_instruction("100.00", start, denomination="USD"),
                    # this brings the daily balance below MAB
                    # but after sampling time, hence not impacting
                    # mean calculation
                    create_outbound_hard_settlement_instruction(
                        "1.00", after_1st_fee_sampling_time, denomination="USD"
                    ),
                ],
                expected_balances_at_ts={
                    after_1st_fees_application: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "99.00"),
                        ],
                        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                    }
                },
            ),
            SubTest(
                description="using lowest indexed one when multiple tiers assigned",
                events=[
                    create_flag_event(
                        timestamp=after_1st_fees_application,
                        expiry_timestamp=end,
                        flag_definition_id="Y",
                        account_id="Main account",
                    )
                ],
            ),
            SubTest(
                # Balance dips below from end of penultimate day in the month
                # Balance goes back above MAB after sampling time
                # --> one MAB fee charged
                description="fee charged when mean balance below threshold at sampling time ",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "200.00", before_2nd_fees_application, denomination="USD"
                    )
                ],
                # 100 - 1 = 99 at sampling time
                # deposit after sampling time 200 + 99 = 299
                # average below MAB so 100 fee charged, 299 - 100 = 199
                expected_balances_at_ts={
                    after_2nd_fees_application: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "199.00"),
                        ],
                        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "100"),
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
        )

        self.run_test_scenario(test_scenario)

    def test_minimum_balance_fee_eod_sampling_time(self):
        start = datetime(year=2021, month=3, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=4, day=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "minimum_balance_fee": "100",
            "tier_names": dumps(["X", "Y", "Z"]),
            "minimum_balance_threshold": dumps({"X": "100", "Y": "300", "Z": "500"}),
            "maintenance_fee_monthly": dumps({"X": "0", "Y": "0", "Z": "0"}),
            "minimum_combined_balance_threshold": dumps({"X": "5000", "Y": "5000", "Z": "5000"}),
            "minimum_deposit_threshold": dumps({"X": "500", "Y": "500", "Z": "500"}),
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
            "fees_application_hour": "23",
            "fees_application_minute": "59",
            "fees_application_second": "58",
        }

        def get_events_to_oscillate_balance(year, month):
            events = []
            for i in range(1, 32):
                instruction = (
                    create_inbound_hard_settlement_instruction
                    if i % 2 == 0
                    else create_outbound_hard_settlement_instruction
                )
                events.append(
                    instruction(
                        "2.00",
                        datetime(year=year, month=month, day=i, hour=22, tzinfo=timezone.utc),
                        denomination="USD",
                    )
                )
            return events

        oscillation_events = get_events_to_oscillate_balance(2021, 3)

        sub_tests = [
            SubTest(
                description="tiered value is correct after flag expiry",
                events=[
                    create_flag_definition_event(timestamp=start, flag_definition_id="X"),
                    create_flag_definition_event(timestamp=start, flag_definition_id="Y"),
                    create_flag_definition_event(timestamp=start, flag_definition_id="Z"),
                    create_flag_event(
                        timestamp=start,
                        expiry_timestamp=start + timedelta(days=2),
                        flag_definition_id="X",
                        account_id="Main account",
                    ),
                    create_flag_event(
                        timestamp=start,
                        expiry_timestamp=end,
                        flag_definition_id="Y",
                        account_id="Main account",
                    ),
                ],
            ),
            SubTest(
                # balance fluctuates between 298.99 and 300.99
                # and ends at 298.99, average is below MAB
                # so incurs a fee of 100 at the end of the month
                description="fluctuating balance with average below MAB",
                events=[
                    # set balance to be 300.99
                    create_inbound_hard_settlement_instruction("300.99", start, denomination="USD"),
                    *oscillation_events,
                ],
                expected_balances_at_ts={
                    end: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "198.99"),
                        ],
                        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "100"),
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
        )

        self.run_test_scenario(test_scenario)

    def test_configurable_interest_accrual_and_application_time(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=2, day=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.03"}),
            "interest_accrual_hour": "22",
            "interest_accrual_minute": "59",
            "interest_accrual_second": "59",
            "interest_application_hour": "23",
            "interest_application_minute": "59",
            "interest_application_second": "1",
        }

        sub_tests = [
            SubTest(
                description="interest accrual runs at configured time",
                events=[
                    create_inbound_hard_settlement_instruction("100.00", start, denomination="USD")
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2021,
                                month=1,
                                day=1,
                                hour=22,
                                minute=59,
                                second=59,
                                tzinfo=timezone.utc,
                            )
                        ],
                        event_id="ACCRUE_INTEREST_AND_DAILY_FEES",
                        account_id="Main account",
                        count=32,
                    )
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    @unittest.skip("Changing parameter causes schedule to run twice - INC-4286 to fix")
    def test_interest_application_monthly_only_once_per_month(self):
        start = datetime(year=2019, month=12, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=3, day=1, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.03"}),
            "deposit_interest_application_frequency": "monthly",
            "interest_application_hour": "23",
            "interest_application_minute": "59",
            "interest_application_second": "59",
        }
        instance_params = {
            **default_instance_params,
            "interest_application_day": "4",
        }

        # Only 1 interest application per month
        apply_interest_schedule_before_change = self._create_list_of_schedule_datetimes(
            start=datetime(
                year=2019,
                month=12,
                day=4,
                hour=23,
                minute=59,
                second=59,
                tzinfo=timezone.utc,
            ),
            end=start + timedelta(months=2, hours=2),
            frequency="monthly",
        )

        expected_feb = datetime(
            year=2020,
            month=2,
            day=29,
            hour=23,
            minute=59,
            second=59,
            tzinfo=timezone.utc,
        )

        sub_tests = [
            SubTest(
                description="Only 1 interest application per month",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + timedelta(months=1, hours=2),
                        account_id="Main account",
                        interest_application_day="31",
                    ),
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=apply_interest_schedule_before_change,
                        event_id="APPLY_ACCRUED_DEPOSIT_INTEREST",
                        account_id="Main account",
                        count=3,
                    ),
                    ExpectedSchedule(
                        run_times=[expected_feb],
                        event_id="APPLY_ACCRUED_DEPOSIT_INTEREST",
                        account_id="Main account",
                        count=3,
                    ),
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

    def test_interest_application_monthly_defaults_to_end_of_month(self):
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=5, day=1, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.03"}),
            "deposit_interest_application_frequency": "monthly",
            "interest_application_hour": "23",
            "interest_application_minute": "59",
            "interest_application_second": "59",
        }
        instance_params = {
            **default_instance_params,
            "interest_application_day": "31",
        }

        expected_first_month = datetime(
            year=2020,
            month=1,
            day=31,
            hour=23,
            minute=59,
            second=59,
            tzinfo=timezone.utc,
        )

        # Check schedule handles leap year
        expected_february_leap_year = datetime(
            year=2020,
            month=2,
            day=29,
            hour=23,
            minute=59,
            second=59,
            tzinfo=timezone.utc,
        )

        expected_third_month = datetime(
            year=2020,
            month=3,
            day=31,
            hour=23,
            minute=59,
            second=59,
            tzinfo=timezone.utc,
        )

        expected_fourth_month = datetime(
            year=2020,
            month=3,
            day=31,
            hour=23,
            minute=59,
            second=59,
            tzinfo=timezone.utc,
        )

        sub_tests = [
            SubTest(
                description="Schedule defaults to end of month",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_first_month,
                            expected_february_leap_year,
                            expected_third_month,
                            expected_fourth_month,
                        ],
                        event_id="APPLY_ACCRUED_DEPOSIT_INTEREST",
                        account_id="Main account",
                        count=4,
                    ),
                ],
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_interest_application_quarterly(self):
        start = datetime(year=2020, month=1, day=5, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=10, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.03"}),
            "deposit_interest_application_frequency": "quarterly",
            "interest_application_hour": "23",
            "interest_application_minute": "59",
            "interest_application_second": "59",
        }
        instance_params = {
            **default_instance_params,
            "interest_application_day": "4",
        }

        expected_1st_quarter = datetime(
            year=2020,
            month=4,
            day=4,
            hour=23,
            minute=59,
            second=59,
            tzinfo=timezone.utc,
        )
        expected_2nd_quarter = datetime(
            year=2020,
            month=7,
            day=4,
            hour=23,
            minute=59,
            second=59,
            tzinfo=timezone.utc,
        )
        expected_3rd_quarter = datetime(
            year=2020,
            month=10,
            day=4,
            hour=23,
            minute=59,
            second=59,
            tzinfo=timezone.utc,
        )
        expected_4th_quarter = datetime(
            year=2021,
            month=1,
            day=4,
            hour=23,
            minute=59,
            second=59,
            tzinfo=timezone.utc,
        )

        sub_tests = [
            SubTest(
                description="interest application runs quarterly",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            expected_1st_quarter,
                            expected_2nd_quarter,
                            expected_3rd_quarter,
                            expected_4th_quarter,
                        ],
                        event_id="APPLY_ACCRUED_DEPOSIT_INTEREST",
                        account_id="Main account",
                        count=4,
                    )
                ],
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_interest_application_annually(self):
        start = datetime(year=2020, month=1, day=5, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=12, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.06"}),
            "deposit_interest_application_frequency": "annually",
            "interest_application_hour": "23",
            "interest_application_minute": "59",
            "interest_application_second": "59",
        }
        instance_params = {
            **default_instance_params,
            "interest_application_day": "10",
        }

        sub_tests = [
            SubTest(
                description="interest application runs annually",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "1000.00", end - timedelta(days=1), denomination="USD"
                    )
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2021,
                                month=1,
                                day=10,
                                hour=23,
                                minute=59,
                                second=59,
                                tzinfo=timezone.utc,
                            )
                        ],
                        event_id="APPLY_ACCRUED_DEPOSIT_INTEREST",
                        account_id="Main account",
                        count=1,
                    )
                ],
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_schedules(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=7, hour=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "fees_application_day": "3",
            "fees_application_hour": "23",
            "fees_application_minute": "59",
            "fees_application_second": "59",
        }

        accrue_interest_schedule = self._create_list_of_schedule_datetimes(
            start=datetime(
                year=2019,
                month=1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                tzinfo=timezone.utc,
            ),
            end=end,
            frequency="daily",
        )

        apply_monthly_fees_datetime = self._create_list_of_schedule_datetimes(
            start=datetime(
                year=2019,
                month=2,
                day=3,
                hour=23,
                minute=59,
                second=59,
                tzinfo=timezone.utc,
            ),
            end=end,
            frequency="monthly",
        )

        sub_tests = [
            SubTest(
                description="check schedules are created as expected",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=accrue_interest_schedule,
                        count=len(accrue_interest_schedule),
                        event_id="ACCRUE_INTEREST_AND_DAILY_FEES",
                        account_id="Main account",
                    ),
                    ExpectedSchedule(
                        run_times=apply_monthly_fees_datetime,
                        count=len(apply_monthly_fees_datetime),
                        event_id="APPLY_MONTHLY_FEES",
                        account_id="Main account",
                    ),
                ],
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )

        self.run_test_scenario(test_scenario)

    def test_posting_denominations(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=1, hour=14, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="multiple currencies supported",
                events=[
                    create_inbound_hard_settlement_instruction("100.00", start, denomination="EUR"),
                    create_inbound_hard_settlement_instruction("100.00", start, denomination="GBP"),
                    create_outbound_hard_settlement_instruction(
                        "50.00", start + timedelta(minutes=2), denomination="GBP"
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(minutes=5): {
                        "Main account": [
                            (BalanceDimensions(denomination="GBP"), "50.00"),
                            (BalanceDimensions(denomination="EUR"), "100.00"),
                        ]
                    }
                },
            ),
            SubTest(
                description="additional currencies cannot go into negative balance",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "100.00", start + timedelta(minutes=30), denomination="GBP"
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(minutes=30),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total GBP -100.00, which exceeds the available"
                        " balance of GBP 50",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(minutes=35): {
                        "Main account": [
                            (BalanceDimensions(denomination="GBP"), "50.00"),
                            (BalanceDimensions(denomination="EUR"), "100.00"),
                        ]
                    }
                },
            ),
            SubTest(
                description="unsupported currencies are rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100.00", start + timedelta(hours=1), denomination="CNY"
                    ),
                    create_outbound_hard_settlement_instruction(
                        "100.00",
                        start + timedelta(hours=1, minutes=5),
                        denomination="HKD",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + timedelta(hours=1),
                        rejection_type="WrongDenomination",
                        rejection_reason="Postings received in unauthorised denominations CNY.",
                    ),
                    ExpectedRejection(
                        start + timedelta(hours=1, minutes=5),
                        rejection_type="WrongDenomination",
                        rejection_reason="Postings received in unauthorised denominations HKD.",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=10): {
                        "Main account": [
                            (BalanceDimensions(denomination="CNY"), "0.00"),
                            (BalanceDimensions(denomination="HKD"), "0.00"),
                        ]
                    }
                },
            ),
            SubTest(
                description="multiple additional currencies in one batch can be accepted",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            InboundHardSettlement(
                                "200",
                                target_account_id="Main account",
                                denomination="EUR",
                            ),
                            InboundHardSettlement(
                                "3000",
                                target_account_id="Main account",
                                denomination="GBP",
                            ),
                            InboundHardSettlement(
                                "1000",
                                target_account_id="Main account",
                                denomination="USD",
                            ),
                        ],
                        event_datetime=start + timedelta(hours=2),
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=2, minutes=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="EUR"), "300.00"),
                            (BalanceDimensions(denomination="GBP"), "3050.00"),
                            (BalanceDimensions(denomination="USD"), "1000.00"),
                        ]
                    }
                },
            ),
            SubTest(
                description="entire batch is rejected if main denom exceeds standard overdraft \
                    limit",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                "100",
                                target_account_id="Main account",
                                denomination="EUR",
                            ),
                            InboundHardSettlement(
                                "3000",
                                target_account_id="Main account",
                                denomination="GBP",
                            ),
                            OutboundHardSettlement(
                                "1500",
                                target_account_id="Main account",
                                denomination="USD",
                            ),
                            OutboundHardSettlement(
                                "2000",
                                target_account_id="Main account",
                                denomination="USD",
                            ),
                        ],
                        event_datetime=start + timedelta(hours=3),
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + timedelta(hours=3),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Posting exceeds standard_overdraft_limit",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=3, minutes=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="EUR"), "300.00"),
                            (BalanceDimensions(denomination="GBP"), "3050.00"),
                            (BalanceDimensions(denomination="USD"), "1000.00"),
                        ]
                    }
                },
            ),
            SubTest(
                description="entire batch is rejected if unsupported denomination is present",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            InboundHardSettlement(
                                "100",
                                target_account_id="Main account",
                                denomination="JPY",
                            ),
                            InboundHardSettlement(
                                "3000",
                                target_account_id="Main account",
                                denomination="GBP",
                            ),
                            InboundHardSettlement(
                                "1500",
                                target_account_id="Main account",
                                denomination="USD",
                            ),
                        ],
                        event_datetime=start + timedelta(hours=4),
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + timedelta(hours=4),
                        rejection_type="WrongDenomination",
                        rejection_reason="Postings received in unauthorised denominations JPY.",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=4, minutes=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="EUR"), "300.00"),
                            (BalanceDimensions(denomination="GBP"), "3050.00"),
                            (BalanceDimensions(denomination="USD"), "1000.00"),
                        ]
                    }
                },
            ),
            SubTest(
                description="entire batch is accepted if credit greater than debit",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            InboundHardSettlement(
                                "3000",
                                target_account_id="Main account",
                                denomination="GBP",
                            ),
                            OutboundHardSettlement(
                                "4000",
                                target_account_id="Main account",
                                denomination="GBP",
                            ),
                            InboundHardSettlement(
                                "1500",
                                target_account_id="Main account",
                                denomination="USD",
                            ),
                            OutboundHardSettlement(
                                "3000",
                                target_account_id="Main account",
                                denomination="USD",
                            ),
                        ],
                        event_datetime=start + timedelta(hours=5),
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=5, minutes=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="EUR"), "300.00"),
                            (BalanceDimensions(denomination="GBP"), "2050.00"),
                            (BalanceDimensions(denomination="USD"), "-500.00"),
                        ]
                    }
                },
            ),
            SubTest(
                description="outbound auth reduces available balance",
                events=[
                    create_outbound_authorisation_instruction(
                        "100.00",
                        start + timedelta(hours=6),
                        denomination="EUR",
                        client_transaction_id="outbound_auth",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "250.00",
                        start + timedelta(hours=6, minutes=5),
                        denomination="EUR",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + timedelta(hours=6, minutes=5),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total EUR -250.00, which exceeds the available"
                        " balance of EUR 200",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=6, minutes=10): {
                        "Main account": [
                            (BalanceDimensions(denomination="GBP"), "2050.00"),
                            (BalanceDimensions(denomination="USD"), "-500.00"),
                            (BalanceDimensions(denomination="EUR"), "300.00"),
                            (
                                BalanceDimensions(
                                    denomination="EUR",
                                    phase="POSTING_PHASE_PENDING_OUTGOING",
                                ),
                                "-100.00",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="inbound auth does not affect available balance",
                events=[
                    create_inbound_authorisation_instruction(
                        "300.00",
                        start + timedelta(hours=7),
                        denomination="EUR",
                        client_transaction_id="inbound_auth",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "250.00",
                        start + timedelta(hours=7, minutes=5),
                        denomination="EUR",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + timedelta(hours=7, minutes=5),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total EUR -250.00, which exceeds the available"
                        " balance of EUR 200",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=7, minutes=10): {
                        "Main account": [
                            (BalanceDimensions(denomination="GBP"), "2050.00"),
                            (BalanceDimensions(denomination="USD"), "-500.00"),
                            (BalanceDimensions(denomination="EUR"), "300.00"),
                            (
                                BalanceDimensions(
                                    denomination="EUR",
                                    phase="POSTING_PHASE_PENDING_OUTGOING",
                                ),
                                "-100.00",
                            ),
                            (
                                BalanceDimensions(
                                    denomination="EUR",
                                    phase="POSTING_PHASE_PENDING_INCOMING",
                                ),
                                "300.00",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="outbound auth can be over settled",
                events=[
                    create_settlement_event(
                        amount="100.00",
                        client_transaction_id="outbound_auth",
                        event_datetime=start + timedelta(hours=8),
                    ),
                    create_settlement_event(
                        amount="300.00",
                        client_transaction_id="outbound_auth",
                        event_datetime=start + timedelta(hours=8, minutes=5),
                        final=True,
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=8, minutes=10): {
                        "Main account": [
                            (BalanceDimensions(denomination="GBP"), "2050.00"),
                            (BalanceDimensions(denomination="USD"), "-500.00"),
                            (BalanceDimensions(denomination="EUR"), "-100.00"),
                            (
                                BalanceDimensions(
                                    denomination="EUR",
                                    phase="POSTING_PHASE_PENDING_OUTGOING",
                                ),
                                "0.00",
                            ),
                            (
                                BalanceDimensions(
                                    denomination="EUR",
                                    phase="POSTING_PHASE_PENDING_INCOMING",
                                ),
                                "300.00",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="when balance is -ve due to oversettlement, "
                "further withdrawals are rejected while deposits are accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "20.00", start + timedelta(hours=9), denomination="EUR"
                    ),
                    create_inbound_hard_settlement_instruction(
                        "50.00",
                        start + timedelta(hours=9, minutes=5),
                        denomination="EUR",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + timedelta(hours=9),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total EUR -20.00, which exceeds the available"
                        " balance of EUR -100",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=9, minutes=10): {
                        "Main account": [
                            (BalanceDimensions(denomination="EUR"), "-50.00"),
                            (BalanceDimensions(denomination="GBP"), "2050.00"),
                            (BalanceDimensions(denomination="USD"), "-500.00"),
                            (
                                BalanceDimensions(
                                    denomination="EUR",
                                    phase="POSTING_PHASE_PENDING_OUTGOING",
                                ),
                                "0.00",
                            ),
                            (
                                BalanceDimensions(
                                    denomination="EUR",
                                    phase="POSTING_PHASE_PENDING_INCOMING",
                                ),
                                "300.00",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="outbound auth adjustment is rejected if bringing balance to -ve",
                events=[
                    create_outbound_authorisation_instruction(
                        "2000.00",
                        start + timedelta(hours=10),
                        denomination="GBP",
                        client_transaction_id="another_outbound_auth",
                    ),
                    create_auth_adjustment_instruction(
                        "100.00",
                        event_datetime=start + timedelta(hours=10, minutes=5),
                        client_transaction_id="another_outbound_auth",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + timedelta(hours=10, minutes=5),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total GBP -100.00, which exceeds the available"
                        " balance of GBP 50",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=10, minutes=10): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "-500.00"),
                            (BalanceDimensions(denomination="EUR"), "-50.00"),
                            (BalanceDimensions(denomination="GBP"), "2050.00"),
                            (
                                BalanceDimensions(
                                    denomination="EUR",
                                    phase="POSTING_PHASE_PENDING_OUTGOING",
                                ),
                                "0.00",
                            ),
                            (
                                BalanceDimensions(
                                    denomination="EUR",
                                    phase="POSTING_PHASE_PENDING_INCOMING",
                                ),
                                "300.00",
                            ),
                            (
                                BalanceDimensions(
                                    denomination="GBP",
                                    phase="POSTING_PHASE_PENDING_OUTGOING",
                                ),
                                "-2000.00",
                            ),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests
        )

        self.run_test_scenario(test_scenario)

    @unittest.skip("Test fails consistently due to simulation endpoint issues")
    def test_dormancy(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2022, month=1, day=2, tzinfo=timezone.utc)

        before_1st_monthly_fees = datetime(year=2021, month=2, day=1, tzinfo=timezone.utc)
        after_1st_monthly_fees = before_1st_monthly_fees + timedelta(minutes=2)

        before_2nd_monthly_fees = datetime(year=2021, month=3, day=1, tzinfo=timezone.utc)
        after_2nd_monthly_fees = before_2nd_monthly_fees + timedelta(minutes=2)

        before_3rd_monthly_fees = datetime(year=2021, month=4, day=1, tzinfo=timezone.utc)
        after_3rd_monthly_fees = before_3rd_monthly_fees + timedelta(minutes=2)

        before_annual_fee_applied = datetime(year=2022, month=1, day=1, tzinfo=timezone.utc)
        after_annual_fee_applied = before_annual_fee_applied + timedelta(minutes=2)

        first_dormancy_start = start + timedelta(hours=1)
        first_dormancy_end = after_1st_monthly_fees

        second_dormancy_start = after_2nd_monthly_fees + timedelta(hours=1)
        second_dormancy_end = end

        template_params = {
            **default_template_params,
            "maintenance_fee_monthly": dumps({"US_CHECKING_ACCOUNT_TIER_LOWER": "10"}),
            "minimum_balance_fee": "15",
        }

        sub_tests = [
            SubTest(
                description="dormant account rejects postings",
                events=[
                    create_flag_definition_event(timestamp=start, flag_definition_id=DORMANCY_FLAG),
                    create_inbound_hard_settlement_instruction("100.00", start, denomination="USD"),
                    create_flag_event(
                        timestamp=first_dormancy_start,
                        expiry_timestamp=first_dormancy_end,
                        flag_definition_id=DORMANCY_FLAG,
                        account_id="Main account",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "100.00",
                        start + timedelta(hours=1, minutes=5),
                        denomination="USD",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "50.00",
                        start + timedelta(hours=1, minutes=6),
                        denomination="USD",
                    ),
                    create_outbound_authorisation_instruction(
                        "50.00",
                        start + timedelta(hours=1, minutes=7),
                        denomination="USD",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + timedelta(hours=1, minutes=5),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason='Account flagged \\"Dormant\\" does not '
                        "accept external transactions.",
                    ),
                    ExpectedRejection(
                        start + timedelta(hours=1, minutes=6),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason='Account flagged \\"Dormant\\" does not '
                        "accept external transactions.",
                    ),
                    ExpectedRejection(
                        start + timedelta(hours=1, minutes=7),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason='Account flagged \\"Dormant\\" does not '
                        "accept external transactions.",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=10): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "100.00"),
                            (
                                BalanceDimensions(
                                    denomination="USD",
                                    phase="POSTING_PHASE_PENDING_OUTGOING",
                                ),
                                "0.00",
                            ),
                            (
                                BalanceDimensions(address="ACCRUED_DEPOSIT", denomination="USD"),
                                "0.00",
                            ),
                        ]
                    }
                },
            ),
            SubTest(
                description="dormant account accrues deposit interest",
                expected_balances_at_ts={
                    start
                    + timedelta(days=1, hours=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "100.00"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_PAYABLE",
                                    denomination="USD",
                                ),
                                "0.0137",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "-0.0137",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.0137"),
                        ],
                        INTEREST_PAID_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.0137"),
                        ],
                        INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                    }
                },
            ),
            SubTest(
                description="incurs account_inactivity_fee, not maintenance/minimum balance fees",
                expected_balances_at_ts={
                    before_1st_monthly_fees: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "100.00"),
                            # daily accrual = 0.05 / 365 * 100 = 0.01370
                            # total deposit accrual = 0.013710 * 31  =0.4247
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_PAYABLE",
                                    denomination="USD",
                                ),
                                "0.4247",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "-0.4247",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.4247"),
                        ],
                        INTEREST_PAID_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.4247"),
                        ],
                        INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                    },
                    # 100 - 55 account_inactivity_fee + 0.42 deposit interest = 45.42
                    after_1st_monthly_fees: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "45.42"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_PAYABLE",
                                    denomination="USD",
                                ),
                                "0.00",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "0.00",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                        INTEREST_PAID_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.42"),
                        ],
                        INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "55"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                    },
                },
            ),
            SubTest(
                description="expired dormancy stops account_inactivity_fee",
                expected_balances_at_ts={
                    before_2nd_monthly_fees: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "45.42"),
                            # daily accrual = 0.05 / 365 * 45.42 = 0.00622
                            # total deposit accrual = 0.013710 * 28  =0.17416
                            # total paid interest = 0.42 + 0.17416 = 0.59416
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_PAYABLE",
                                    denomination="USD",
                                ),
                                "0.17416",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "-0.17416",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.17416"),
                        ],
                        INTEREST_PAID_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.59416"),
                        ],
                        INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "55"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                    },
                    # 45.42 - 10 maintenance - 15 minimum balance fee +
                    # 0.17 deposit interest = 20.59
                    after_2nd_monthly_fees: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "20.59"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_DEPOSIT_PAYABLE",
                                    denomination="USD",
                                ),
                                "0.00",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "0.00",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                        INTEREST_PAID_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.59"),
                        ],
                        INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "55"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "10"),
                        ],
                        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "15"),
                        ],
                    },
                },
            ),
            SubTest(
                description="dormant account accrues overdraft interest",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "220.59",
                        after_2nd_monthly_fees + timedelta(minutes=10),
                        denomination="USD",
                    ),
                    create_flag_event(
                        timestamp=second_dormancy_start,
                        expiry_timestamp=second_dormancy_end,
                        flag_definition_id=DORMANCY_FLAG,
                        account_id="Main account",
                    ),
                ],
                expected_balances_at_ts={
                    before_3rd_monthly_fees: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "-200.00"),
                            # daily accrual = 0.1485 / 365 * (-200+50) = -0.06103
                            # total deposit accrual = -0.06103 * 31 = -1.89193
                            (
                                BalanceDimensions(
                                    address="ACCRUED_OVERDRAFT_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "-1.89193",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "1.89193",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                        INTEREST_PAID_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.59"),
                        ],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "1.89193"),
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "1.89193"),
                        ],
                        INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "55"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "10"),
                        ],
                        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "15"),
                        ],
                    },
                    # -200 - 55 account_inactivity_fee - 1.89 overdraft interest = -256.89
                    after_3rd_monthly_fees: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "-256.89"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_OVERDRAFT_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "0.00",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "0.00",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                        INTEREST_PAID_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.59"),
                        ],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "1.89"),
                        ],
                        INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "110"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "10"),
                        ],
                        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "15"),
                        ],
                    },
                },
            ),
            SubTest(
                description="annual maintenance fee not charged",
                expected_balances_at_ts={
                    before_annual_fee_applied: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "-737.93"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_OVERDRAFT_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "-8.67628",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "8.67628",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                        INTEREST_PAID_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.59"),
                        ],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "8.67628"),
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "51.60628"),
                        ],
                        INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "550"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "10"),
                        ],
                        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "15"),
                        ],
                    },
                    # -737.93 - 55 account_inactivity_fee - 8.68 overdraft interest = -801.61
                    after_annual_fee_applied: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "-801.61"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_OVERDRAFT_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "0.00",
                            ),
                            (
                                BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"),
                                "0.00",
                            ),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                        INTEREST_PAID_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.59"),
                        ],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "51.61"),
                        ],
                        INACTIVITY_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "605"),
                        ],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "10"),
                        ],
                        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "15"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )

        self.run_test_scenario(test_scenario)

    def test_auto_save(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=1, hour=12, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "autosave_rounding_amount": "1.00",
        }
        instance_params = {
            **default_instance_params,
            "autosave_savings_account": "test_savings_account",
        }

        sub_tests = [
            SubTest(
                description="outbound purchase with enough balance auto saves expected amount",
                events=[
                    # inbound does not trigger auto save
                    create_inbound_hard_settlement_instruction(
                        "1000.01", start + timedelta(minutes=10), denomination="USD"
                    ),
                    # round to the next dollar, saves 55 cents
                    create_outbound_hard_settlement_instruction(
                        "283.45", start + timedelta(minutes=11), denomination="USD"
                    ),
                    # round to the next dollar, saves 99 cents
                    create_outbound_hard_settlement_instruction(
                        "515.01", start + timedelta(minutes=12), denomination="USD"
                    ),
                    # no auto save
                    create_outbound_hard_settlement_instruction(
                        "88.00", start + timedelta(minutes=13), denomination="USD"
                    ),
                    # remaining balance is 112.01, auto save does not trigger
                    create_outbound_hard_settlement_instruction(
                        "112.01", start + timedelta(minutes=14), denomination="USD"
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(minutes=30): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "0.00")],
                        # 0.99 + 0.55 = 1.54
                        "test_savings_account": [(BalanceDimensions(denomination="USD"), "1.54")],
                    }
                },
            ),
            SubTest(
                description="additional denomination do not trigger auto save",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(hours=1, minutes=10),
                        denomination="GBP",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "1000",
                        start + timedelta(hours=1, minutes=10),
                        denomination="EUR",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "283.45",
                        start + timedelta(hours=1, minutes=11),
                        denomination="EUR",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "515.01",
                        start + timedelta(hours=1, minutes=11),
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=30): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "0.00"),
                            (BalanceDimensions(denomination="EUR"), "716.55"),
                            (BalanceDimensions(denomination="GBP"), "484.99"),
                        ],
                        "test_savings_account": [
                            (BalanceDimensions(denomination="USD"), "1.54"),
                            (BalanceDimensions(denomination="EUR"), "0.00"),
                            (BalanceDimensions(denomination="GBP"), "0.00"),
                        ],
                    }
                },
            ),
            SubTest(
                description="auto save is not triggered when there is minimum balance fee",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(hours=2),
                        minimum_balance_fee="20",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "1000.00",
                        start + timedelta(hours=2, minutes=10),
                        denomination="USD",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "283.45",
                        start + timedelta(hours=2, minutes=11),
                        denomination="USD",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=2, minutes=30): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "716.55")],
                        "test_savings_account": [(BalanceDimensions(denomination="USD"), "1.54")],
                    }
                },
            ),
            SubTest(
                description="auto save other rounding amount",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(hours=3),
                        minimum_balance_fee="0.00",
                    ),
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(hours=3),
                        autosave_rounding_amount="2.50",
                    ),
                    create_inbound_hard_settlement_instruction(
                        "10000.00",
                        start + timedelta(hours=3, minutes=10),
                        denomination="USD",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "4800.20",
                        start + timedelta(hours=3, minutes=11),
                        denomination="USD",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=3, minutes=30): {
                        # 4800.20 + 2.30 rounding = 4802.50 (rounded to 2.50)
                        # 716.55 + 10000 - 4802.50 = 5914.05
                        "Main account": [(BalanceDimensions(denomination="USD"), "5914.05")],
                        # 1.54 + 2.30 = 3.84
                        "test_savings_account": [(BalanceDimensions(denomination="USD"), "3.84")],
                    }
                },
            ),
            SubTest(
                description="multiple postings in a batch triggers auto save correctly",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(hours=4),
                        autosave_rounding_amount="1.00",
                    ),
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                "99.05",
                                target_account_id="Main account",
                                denomination="USD",
                            ),
                            OutboundHardSettlement(
                                "49.75",
                                target_account_id="Main account",
                                denomination="USD",
                            ),
                        ],
                        event_datetime=start + timedelta(hours=4, minutes=10),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=4, minutes=30): {
                        # 99.05 + 0.95 rounding = 100
                        # 49.75 + 0.25 rounding = 50
                        # 5914.05 - 100 - 50 = 5764.05
                        "Main account": [(BalanceDimensions(denomination="USD"), "5764.05")],
                        # 3.84 + 0.95 + 0.25 = 5.04
                        "test_savings_account": [(BalanceDimensions(denomination="USD"), "5.04")],
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
            internal_accounts={"1": "LIABILITY", "test_savings_account": "LIABILITY"},
        )

        self.run_test_scenario(test_scenario)

    def test_overdraft_transaction_fee(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=1, hour=10, tzinfo=timezone.utc)

        # Set standard_overdraft_fee_cap to 0 to test it is unlimited
        template_params = {
            **default_template_params,
            "standard_overdraft_per_transaction_fee": "34",
            "standard_overdraft_daily_fee": "1",
            "standard_overdraft_fee_cap": "0",
        }

        sub_tests = [
            SubTest(
                description="overdraft per transaction fee is incurred",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "1500",
                        start + timedelta(hours=1, minutes=10),
                        denomination="USD",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=30): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-1534")],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "34"),
                        ],
                    }
                },
            ),
            SubTest(
                description="fee free overdraft",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "1534",
                        start + timedelta(hours=2, minutes=10),
                        denomination="USD",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "999",
                        start + timedelta(hours=2, minutes=11),
                        denomination="USD",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=2, minutes=30): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-999")],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "34"),
                        ],
                    }
                },
            ),
            SubTest(
                description="overdraft transaction fee not applied on rejected withdrawal",
                events=[
                    create_outbound_hard_settlement_instruction(
                        "2000",
                        start + timedelta(hours=3, minutes=10),
                        denomination="USD",
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=3, minutes=10),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Posting exceeds standard_overdraft_limit",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=3, minutes=30): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-999")],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "34"),
                        ],
                    }
                },
            ),
            SubTest(
                description="not applied on deposits",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "500",
                        start + timedelta(hours=4, minutes=10),
                        denomination="USD",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=4, minutes=30): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-499")],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "34"),
                        ],
                    }
                },
            ),
            SubTest(
                description="overdraft fee applied to custom instruction on default address",
                events=[
                    create_custom_instruction(
                        amount="1000",
                        creditor_target_account_id="1",
                        debtor_target_account_id="Main account",
                        creditor_target_account_address="DEFAULT",
                        debtor_target_account_address="DEFAULT",
                        event_datetime=start + timedelta(hours=5, minutes=10),
                        denomination="USD",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=5, minutes=30): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-1533")],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "68"),
                        ],
                    }
                },
            ),
            SubTest(
                description="two overdrafts in one batch incur fee twice",
                events=[
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                "100.00",
                                target_account_id="Main account",
                                denomination="USD",
                            ),
                            OutboundHardSettlement(
                                "50.00",
                                target_account_id="Main account",
                                denomination="USD",
                            ),
                        ],
                        event_datetime=start + timedelta(hours=6, minutes=10),
                    )
                ],
                expected_balances_at_ts={
                    # -1533 - 100 - 50 - 34 - 34 = -1751
                    start
                    + timedelta(hours=6, minutes=30): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-1751")],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "136"),
                        ],
                    }
                },
            ),
            SubTest(
                description="fee cap applied",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(hours=7),
                        standard_overdraft_fee_cap="12.00",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "10", start + timedelta(hours=7, minutes=10), denomination="USD"
                    ),
                    create_inbound_hard_settlement_instruction(
                        "100",
                        start + timedelta(hours=7, minutes=11),
                        denomination="USD",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "10", start + timedelta(hours=7, minutes=12), denomination="USD"
                    ),
                    create_outbound_hard_settlement_instruction(
                        "50", start + timedelta(hours=7, minutes=13), denomination="USD"
                    ),
                ],
                expected_balances_at_ts={
                    # fee cap is lowered so already reached in previous transactions
                    # no further overdraft per transaction fee will be charged
                    # -1751 - 10 = -1761
                    start
                    + timedelta(hours=7, minutes=10, seconds=30): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-1761")]
                    },
                    # -1761 + 100 - 10 - 50 = -1741
                    start
                    + timedelta(hours=7, minutes=30): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-1721")],
                        OVERDRAFT_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "136"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )

        self.run_test_scenario(test_scenario)

    def test_standard_overdraft_transaction_coverage(self):
        start = datetime(year=2021, month=5, day=1, tzinfo=timezone.utc)
        end = start + timedelta(months=1, hours=11)

        template_params = {
            **default_template_params,
            "standard_overdraft_per_transaction_fee": "0",
            "deposit_tier_ranges": dumps({"tier1": {"min": "0"}}),
            "deposit_interest_rate_tiers": dumps({"tier1": "0.00"}),
        }

        sub_tests = [
            SubTest(
                description="Mixed instructions with some not covered",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "200", start + timedelta(minutes=10), denomination="USD"
                    ),
                    # This one should be rejected as the eCommerce code 3123 is not covered
                    create_outbound_hard_settlement_instruction(
                        "210",
                        start + timedelta(minutes=11),
                        denomination="USD",
                        instruction_details={"transaction_code": "3123"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        "230",
                        start + timedelta(minutes=12),
                        denomination="USD",
                        instruction_details={"transaction_code": "other"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(minutes=13): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-30")]
                    }
                },
            ),
            SubTest(
                description="Mixed instructions after flag creation",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "80", start + timedelta(minutes=15), denomination="USD"
                    ),
                    create_flag_definition_event(
                        timestamp=start + timedelta(minutes=16),
                        flag_definition_id=STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG,
                    ),
                    # Creating the flag enables the overdraft coverage for all transaction types
                    create_flag_event(
                        timestamp=start + timedelta(minutes=17),
                        expiry_timestamp=start + timedelta(months=1),
                        flag_definition_id=STANDARD_OVERDRAFT_TRANSACTION_COVERAGE_FLAG,
                        account_id="Main account",
                    ),
                    create_outbound_hard_settlement_instruction(
                        "150",
                        start + timedelta(minutes=18),
                        denomination="USD",
                        instruction_details={"transaction_code": "3123"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        "150",
                        start + timedelta(minutes=19),
                        denomination="USD",
                        instruction_details={"transaction_code": "6011"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(minutes=20): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-250")]
                    }
                },
            ),
            SubTest(
                description="Mixed instructions after flag expiration at 1 month",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "350", start + timedelta(minutes=21), denomination="USD"
                    ),
                    # Coverage flag has expired after 1 month
                    create_outbound_hard_settlement_instruction(
                        "150",
                        start + timedelta(months=1, hours=10, minutes=1),
                        denomination="USD",
                        instruction_details={"transaction_code": "3123"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        "150",
                        start + timedelta(months=1, hours=10, minutes=2),
                        denomination="USD",
                        instruction_details={"transaction_code": "6011"},
                    ),
                    create_outbound_authorisation_instruction(
                        "250.5",
                        start + timedelta(months=1, hours=10, minutes=3),
                        denomination="USD",
                        client_transaction_id="outbound_auth",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(months=1, hours=10, minutes=3): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "100"),
                            (
                                BalanceDimensions(
                                    denomination="USD",
                                    phase="POSTING_PHASE_PENDING_OUTGOING",
                                ),
                                "-250.5",
                            ),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )

        self.run_test_scenario(test_scenario)

    def test_live_rejected_overdraft(self):
        """
        Ensure the live balance is used for overdraft limit with backdated posting

        Scenario:
        A overdraft limit with $2000 USD with a starting balance of $0
        At processing_time=3:00 an outbound withdrawn is made for $1999
        At processing_time=4:00 a backdated outbound withdrawn is made
        with a value timestamp = 2:00 for $5

        Expectation:

        live balance:
        When processing the first posting the contract (pre_posting_code())
        sees the balance of $0 and accepts the posting.
        Then when processing the second posting the contract sees the live balance
        of $1999 and rejects the second posting for exceed overdraft limit.
        """

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="ensure the live balance is used",
                events=[
                    # Set account balance to -1999
                    create_outbound_hard_settlement_instruction(
                        amount="1999.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        value_timestamp=(start + timedelta(hours=3)),
                        event_datetime=(start + timedelta(hours=3)),
                    ),
                    # Attempt to make a withdrawal that would
                    # reduce balance below the standard overdraft limit to -2004 should be rejected
                    create_outbound_hard_settlement_instruction(
                        amount="5.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        value_timestamp=(start + timedelta(hours=2)),
                        event_datetime=(start + timedelta(hours=4)),
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hours=4),
                        rejection_type="InsufficientFunds",
                        rejection_reason="Posting exceeds standard_overdraft_limit",
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=3, minutes=1): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-1999.00")]
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

    def test_credit_posting_not_rejected_even_if_total_is_over_standard_overdraft_limit(
        self,
    ):
        """
        Ensure credit postings are not rejected even if overdraft balance
        is still exceeding the overdraft limit

        Scenario 1 :
        A overdraft limit with $2000 USD with a starting balance of $0
        An debit transaction is made for $2000
        An overdraft fee is calculated for the debit transaction, bringing total balance to -$2005
        A credit transaction worth $1 is made
        Expectation:
        The credit transaction is NOT rejected, despite the predicted total balance still being
        in breach of the overdraft limits of the account

        """

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, minute=4, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "standard_overdraft_per_transaction_fee": "5",
        }

        sub_tests = [
            SubTest(
                description="Scenario 1 as per test method docstring",
                events=[
                    # Set account balance to -2000 + -5(fee) = -2005
                    create_outbound_hard_settlement_instruction(
                        amount="2000.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        value_timestamp=(start + timedelta(minutes=1)),
                        event_datetime=(start + timedelta(minutes=1)),
                    ),
                    # Make a deposit that won't bring balance over the standard overdraft limit
                    create_inbound_hard_settlement_instruction(
                        amount="1.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        value_timestamp=(start + timedelta(minutes=2)),
                        event_datetime=(start + timedelta(minutes=2)),
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(minutes=3): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-2004.00")]
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)


if __name__ == "__main__":
    if any(item.startswith("test") for item in sys.argv):
        unittest.main(USCheckingAccountTest)
    else:
        unittest.main(USCheckingAccountTest())
