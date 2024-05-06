# Copyright @ 2022 Thought Machine Group Limited. All rights reserved.
# standard libs
import json
import sys
import unittest
from ctypes import ArgumentError
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta as timedelta

# library
from library.us_products_v3.constants.files import US_SAVINGS_TEMPLATE

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractModuleConfig,
    ExpectedContractNotification,
    ExpectedRejection,
    ExpectedSchedule,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_hard_settlement_instruction,
    create_posting_instruction_batch,
    create_template_parameter_change_event,
    update_account_status_pending_closure,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase
from inception_sdk.vault.postings.posting_classes import (
    InboundHardSettlement,
    OutboundHardSettlement,
)

CONTRACT_MODULES_ALIAS_FILE_MAP = {
    "utils": "library/common/contract_modules/utils.py",
    "interest": "library/common/contract_modules/interest.py",
}
ASSET_CONTRACT_FILE = "internal_accounts/testing_internal_asset_account_contract.py"
LIABILITY_CONTRACT_FILE = "internal_accounts/testing_internal_liability_account_contract.py"
DEFAULT_DENOMINATION = "USD"
PROMOTIONAL_INTEREST_RATES = "PROMOTIONAL_INTEREST_RATES"
PROMOTIONAL_MAINTENANCE_FEE = "PROMOTIONAL_MAINTENANCE_FEE"
ACCRUED_INTEREST_PAYABLE_ACCOUNT = "ACCRUED_INTEREST_PAYABLE"
INTEREST_PAID_ACCOUNT = "INTEREST_PAID"
ACCRUED_INTEREST_RECEIVABLE_ACCOUNT = "ACCRUED_INTEREST_RECEIVABLE"
INTEREST_RECEIVED_ACCOUNT = "INTEREST_RECEIVED"
MAINTENANCE_FEE_INCOME_ACCOUNT = "MAINTENANCE_FEE_INCOME"
EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT = "EXCESS_WITHDRAWAL_FEE_INCOME"
MINIMUM_BALANCE_FEE_INCOME_ACCOUNT = "MINIMUM_BALANCE_FEE_INCOME"
INTERNAL_CONTRA = "INTERNAL_CONTRA"

BALANCE_TIER_RANGES = json.dumps(
    {
        "tier1": {"min": "0", "max": "15000.00"},
        "tier2": {"min": "15000.00"},
    }
)
TIERED_INTEREST_RATES = json.dumps(
    {
        "UPPER_TIER": {"tier1": "0.02", "tier2": "0.015"},
        "MIDDLE_TIER": {"tier1": "0.0125", "tier2": "0.01"},
        "LOWER_TIER": {"tier1": "0.149", "tier2": "-0.1485"},
    }
)
PROMOTION_RATES = json.dumps(
    {
        "UPPER_TIER": {"tier1": "0.04", "tier2": "0.03"},
        "MIDDLE_TIER": {"tier1": "0.03", "tier2": "0.02"},
        "LOWER_TIER": {"tier1": "0.25", "tier2": "-0.01"},
    }
)
TIERED_MIN_BALANCE_THRESHOLD = json.dumps(
    {
        "UPPER_TIER": "25",
        "MIDDLE_TIER": "75",
        "LOWER_TIER": "100",
    }
)
ZERO_TIERED_MAINTENANCE_FEE_MONTHLY = json.dumps(
    {
        "UPPER_TIER": "0",
        "MIDDLE_TIER": "0",
        "LOWER_TIER": "0",
    }
)
ACCOUNT_TIER_NAMES = json.dumps(
    [
        "UPPER_TIER",
        "MIDDLE_TIER",
        "LOWER_TIER",
    ]
)
ZERO_TIERED_INTEREST_RATES = json.dumps(
    {
        "UPPER_TIER": {"tier1": "0", "tier2": "0"},
        "MIDDLE_TIER": {"tier1": "0", "tier2": "0"},
        "LOWER_TIER": {"tier1": "0", "tier2": "0"},
    }
)

default_template_params = {
    "denomination": "USD",
    "balance_tier_ranges": BALANCE_TIER_RANGES,
    "tiered_interest_rates": TIERED_INTEREST_RATES,
    "minimum_combined_balance_threshold": json.dumps(
        {
            "UPPER_TIER": "3000",
            "MIDDLE_TIER": "4000",
            "LOWER_TIER": "5000",
        }
    ),
    "minimum_deposit": "100",
    "maximum_daily_deposit": "1001",
    "minimum_withdrawal": "0.01",
    "maximum_daily_withdrawal": "100",
    "maximum_balance": "10000",
    "accrued_interest_payable_account": ACCRUED_INTEREST_PAYABLE_ACCOUNT,
    "interest_paid_account": INTEREST_PAID_ACCOUNT,
    "accrued_interest_receivable_account": ACCRUED_INTEREST_RECEIVABLE_ACCOUNT,
    "interest_received_account": INTEREST_RECEIVED_ACCOUNT,
    "maintenance_fee_income_account": MAINTENANCE_FEE_INCOME_ACCOUNT,
    "excess_withdrawal_fee_income_account": EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT,
    "minimum_balance_fee_income_account": MINIMUM_BALANCE_FEE_INCOME_ACCOUNT,
    "days_in_year": "365",
    "interest_accrual_hour": "0",
    "interest_accrual_minute": "0",
    "interest_accrual_second": "0",
    "interest_application_hour": "0",
    "interest_application_minute": "1",
    "interest_application_second": "0",
    "interest_application_frequency": "monthly",
    "monthly_withdrawal_limit": "5",
    "reject_excess_withdrawals": "true",
    "excess_withdrawal_fee": "10",
    "maintenance_fee_monthly": ZERO_TIERED_MAINTENANCE_FEE_MONTHLY,
    "promotional_maintenance_fee_monthly": ZERO_TIERED_MAINTENANCE_FEE_MONTHLY,
    "fees_application_day": "1",
    "fees_application_hour": "0",
    "fees_application_minute": "1",
    "fees_application_second": "0",
    "tiered_minimum_balance_threshold": TIERED_MIN_BALANCE_THRESHOLD,
    "minimum_balance_fee": "0",
    "account_tier_names": ACCOUNT_TIER_NAMES,
    "automated_transfer_tag": "DEPOSIT_ACH_",
    "promotional_rates": PROMOTION_RATES,
}

default_instance_params = {"interest_application_day": "5"}


class USSavingsAccountTest(SimulationTestCase):

    contract_filepaths = [US_SAVINGS_TEMPLATE]
    contract_modules = [
        ContractModuleConfig(alias, file_path)
        for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP.items()
    ]
    contract_version_id = "0"

    internal_accounts = {
        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: "ASSET",
        INTEREST_RECEIVED_ACCOUNT: "LIABILITY",
        ACCRUED_INTEREST_PAYABLE_ACCOUNT: "LIABILITY",
        INTEREST_PAID_ACCOUNT: "ASSET",
        MAINTENANCE_FEE_INCOME_ACCOUNT: "LIABILITY",
        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: "LIABILITY",
        EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT: "LIABILITY",
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
            contract_content=self.smart_contract_path_to_content[US_SAVINGS_TEMPLATE],
            template_params=template_params or default_template_params,
            account_configs=[
                AccountConfig(instance_params=instance_params or default_instance_params)
            ],
            smart_contract_version_id=self.contract_version_id,
            linked_contract_modules=self.contract_modules,
        )
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=internal_accounts or self.internal_accounts,
        )

    def _create_transactions_to_maximum_balance(self, start, days):
        # This will create 10 transactions over 10 days to build up to `maximum_balance`
        events = []
        for i in range(0, days):
            events.append(
                create_inbound_hard_settlement_instruction(
                    amount="1000.00",
                    denomination="USD",
                    target_account_id="Main account",
                    internal_account_id="1",
                    value_timestamp=(start + timedelta(days=i, hours=1)),
                    event_datetime=(start + timedelta(days=i, hours=1)),
                )
            )
        return events

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

    def test_interest_rates_promotion(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=5, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "0",
            "maximum_balance": "0",
            "maximum_daily_withdrawal": "0",
        }

        sub_tests = [
            SubTest(
                description="before promotional period",
                events=[
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=PROMOTIONAL_INTEREST_RATES
                    ),
                    create_inbound_hard_settlement_instruction(
                        "20000", start + timedelta(hours=1), denomination="USD"
                    ),
                ],
                expected_balances_at_ts={
                    # balance tier1 interest = 15000 * 0.149 / 365 = 6.12329
                    # balance tier2 interest = 5000 * -0.1485 / 365 = -2.03425
                    # total interest accrued = 6.12329 - 2.03425 = 4.08904
                    start
                    + timedelta(days=1, hours=1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE", denomination="USD"
                                ),
                                "6.12329",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_RECEIVABLE", denomination="USD"
                                ),
                                "-2.03425",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-6.12329")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-2.03425")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    }
                },
            ),
            SubTest(
                description="within promotional period",
                events=[
                    create_flag_event(
                        timestamp=start + timedelta(days=1, hours=1),
                        expiry_timestamp=start + timedelta(days=3, hours=1),
                        flag_definition_id=PROMOTIONAL_INTEREST_RATES,
                        account_id="Main account",
                    )
                ],
                expected_balances_at_ts={
                    # balance tier1 interest = 15000 * 0.25 / 365 = 10.27397
                    # balance tier2 interest = 5000 * -0.01 / 365 = -0.13699
                    # total interest accrued = 10.27397 - 0.13699 = 10.13698
                    # total balance = 4.08904 + 10.13698 = 14.22602
                    start
                    + timedelta(days=2, hours=1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE", denomination="USD"
                                ),
                                "16.39726",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_RECEIVABLE", denomination="USD"
                                ),
                                "-2.17124",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-16.39726")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-2.17124")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    },
                    # balance tier1 interest = 15000 * 0.25 / 365 = 10.27397
                    # balance tier2 interest = 5000 * -0.01 / 365 = -0.13699
                    # total interest accrued = 10.27397 - 0.13699 = 10.13698
                    # total balance = 14.22602 + 10.13698 = 24.36300
                    start
                    + timedelta(days=3, hours=1): {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE", denomination="USD"
                                ),
                                "26.67123",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_RECEIVABLE", denomination="USD"
                                ),
                                "-2.30823",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-26.67123")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-2.30823")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    },
                },
            ),
            SubTest(
                description="after promotional period",
                expected_balances_at_ts={
                    # balance tier1 interest = 15000 * 0.149 / 365 = 6.12329
                    # balance tier2 interest = 5000 * -0.1485 / 365 = -2.03425
                    # total interest accrued = 6.12329 - 2.03425 = 4.08904
                    # total balance = 24.36300 + 4.08904 = 28.45204
                    end: {
                        "Main account": [
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE", denomination="USD"
                                ),
                                "32.79452",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_RECEIVABLE",
                                    denomination="USD",
                                ),
                                "-4.34248",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-32.79452")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-4.34248")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )
        self.run_test_scenario(test_scenario)

    def test_interest_accrual_and_application(self):
        start = datetime(year=2020, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=2, day=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "0",
            "maximum_balance": "0",
        }
        instance_params = {
            **default_instance_params,
            "interest_application_day": "1",
        }

        before_1st_interest_application = datetime(
            year=2020, month=1, day=31, hour=23, tzinfo=timezone.utc
        )
        after_1st_interest_application = before_1st_interest_application + timedelta(hours=2)

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
                        "15768.45", start + timedelta(hours=4), denomination="USD"
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=5): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "17373.90")]
                    }
                },
            ),
            SubTest(
                description="test balances after tiered interest accrual",
                expected_balances_at_ts={
                    start
                    + timedelta(days=1, hours=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "17373.90"),
                            # balance tier1 interest = 15000 * 0.149 / 365 = 6.12329
                            # balance tier2 interest = 2373.90 * -0.1485 / 365 = -0.96582
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE", denomination="USD"
                                ),
                                "6.12329",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_RECEIVABLE", denomination="USD"
                                ),
                                "-0.96582",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-6.12329")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-0.96582")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    },
                    start
                    + timedelta(days=2, hours=2): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "17373.90"),
                            # balance tier1 interest = 15000 * 0.149 / 365 = 6.12329
                            # balance tier2 interest = 2373.90 * -0.1485 / 365 = -0.96582
                            # total receivable interest = -0.96582 + -0.96582 = 0.29612
                            # total payable interest = 6.12329 + 6.12329 = 12.24658
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE", denomination="USD"
                                ),
                                "12.24658",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_RECEIVABLE", denomination="USD"
                                ),
                                "-1.93164",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-12.24658")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-1.93164")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    },
                },
            ),
            SubTest(
                description="interest application",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            datetime(
                                year=2020,
                                month=2,
                                day=1,
                                hour=0,
                                minute=1,
                                second=0,
                                tzinfo=timezone.utc,
                            )
                        ],
                        event_id="APPLY_ACCRUED_INTEREST",
                        account_id="Main account",
                        count=1,
                    )
                ],
                expected_balances_at_ts={
                    before_1st_interest_application: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "17373.90"),
                            # balance tier1 interest = 15000 * 0.149 / 365 = 6.12329
                            # balance tier2 interest = 2373.90 * -0.1485 / 365 = -0.96582
                            # total receivable interest = -0.96582 * 30 = -28.9746
                            # total payable interest = 6.12329 * 30 = 183.69870
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE", denomination="USD"
                                ),
                                "183.69870",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_RECEIVABLE", denomination="USD"
                                ),
                                "-28.97460",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-183.69870")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-28.97460")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    },
                    after_1st_interest_application: {
                        # total payable accrued = 183.69870 + 6.12329 = 189.82199
                        # total receivable accrued = 28.97460 + 0.96582 = 29.94042
                        # total balance  = 17373.90 + 189.82 - 29.94 = 17533.78
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "17533.78"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE", denomination="USD"
                                ),
                                "0.00",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_RECEIVABLE", denomination="USD"
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
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "189.82")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "29.94")
                        ],
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_monthly_maintenance_fee(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=6, day=1, hour=5, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "0",
            "maximum_balance": "0",
            "maximum_daily_withdrawal": "0",
            "tiered_interest_rates": ZERO_TIERED_INTEREST_RATES,
            "maintenance_fee_monthly": json.dumps({"LOWER_TIER": "20"}),
            "promotional_maintenance_fee_monthly": json.dumps({"LOWER_TIER": "10"}),
        }

        before_monthly_fee_feb = datetime(year=2021, month=2, day=1, tzinfo=timezone.utc)
        after_monthly_fee_feb = before_monthly_fee_feb + timedelta(minutes=2)

        before_monthly_fee_mar = datetime(year=2021, month=3, day=1, tzinfo=timezone.utc)
        after_monthly_fee_mar = before_monthly_fee_mar + timedelta(minutes=2)

        before_monthly_fee_apr = datetime(year=2021, month=4, day=1, tzinfo=timezone.utc)
        after_monthly_fee_apr = before_monthly_fee_apr + timedelta(minutes=2)

        before_monthly_fee_may = datetime(year=2021, month=5, day=1, tzinfo=timezone.utc)
        after_monthly_fee_may = before_monthly_fee_may + timedelta(minutes=2)

        before_monthly_fee_jun = datetime(year=2021, month=6, day=1, tzinfo=timezone.utc)
        after_monthly_fee_jun = before_monthly_fee_jun + timedelta(minutes=2)

        sub_tests = [
            SubTest(
                description="monthly fee can bring balance to negative",
                events=[
                    create_flag_definition_event(
                        timestamp=start, flag_definition_id=PROMOTIONAL_MAINTENANCE_FEE
                    )
                ],
                expected_balances_at_ts={
                    before_monthly_fee_feb: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "0")],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0")
                        ],
                    },
                    after_monthly_fee_feb: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-20")],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "20")
                        ],
                    },
                },
            ),
            SubTest(
                description="charges promotional fee amount during promotional period",
                events=[
                    create_flag_event(
                        timestamp=after_monthly_fee_feb,
                        expiry_timestamp=after_monthly_fee_apr,
                        flag_definition_id=PROMOTIONAL_MAINTENANCE_FEE,
                        account_id="Main account",
                    )
                ],
                expected_balances_at_ts={
                    before_monthly_fee_mar: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-20")],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "20")
                        ],
                    },
                    after_monthly_fee_mar: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "-30")],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "30")
                        ],
                    },
                },
            ),
            SubTest(
                description="manual deposit does not waive maintenance fee",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100",
                        after_monthly_fee_mar + timedelta(days=1),
                        denomination="USD",
                    )
                ],
                expected_balances_at_ts={
                    before_monthly_fee_apr: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "70")],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "30")
                        ],
                    },
                    after_monthly_fee_apr: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "60")],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "40")
                        ],
                    },
                },
            ),
            SubTest(
                description="charges the correct fee after promotional period",
                expected_balances_at_ts={
                    before_monthly_fee_may: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "60")],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "40")
                        ],
                    },
                    after_monthly_fee_may: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "40")],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "60")
                        ],
                    },
                },
            ),
            SubTest(
                description="auto deposit waives maintenance fee",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "100",
                        after_monthly_fee_may + timedelta(days=1),
                        denomination="USD",
                        client_transaction_id="DEPOSIT_ACH_123",
                    )
                ],
                expected_balances_at_ts={
                    before_monthly_fee_jun: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "140")],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "60")
                        ],
                    },
                    after_monthly_fee_jun: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "140")],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "60")
                        ],
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )

        self.run_test_scenario(test_scenario)

    def test_monthly_maintenance_fee_not_applied_if_zero(self):
        """Test that the monthly maintenance fee is not applied if fee is zero"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=1, minute=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "0",
            "maximum_balance": "0",
            "maximum_daily_withdrawal": "0",
            "tiered_interest_rates": ZERO_TIERED_INTEREST_RATES,
            "maintenance_fee_monthly": json.dumps({"LOWER_TIER": "0"}),
            "promotional_maintenance_fee_monthly": json.dumps({"LOWER_TIER": "0"}),
        }

        before_monthly_fee_feb = datetime(year=2021, month=2, day=1, tzinfo=timezone.utc)
        after_monthly_fee_feb = before_monthly_fee_feb + timedelta(minutes=2)

        sub_tests = [
            SubTest(
                description="monthly fee can bring balance to negative",
                expected_balances_at_ts={
                    before_monthly_fee_feb: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "0")],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0")
                        ],
                    },
                    after_monthly_fee_feb: {
                        "Main account": [(BalanceDimensions(denomination="USD"), "0")],
                        MAINTENANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0")
                        ],
                    },
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )

        self.run_test_scenario(test_scenario)

    def test_live_max_balance(self):
        """
        Ensure the live balance is used for maximum limit with backdated posting

        Scenario:
        A maximum balance limit with $10000 USD with a starting balance of $0
        Every day for 10 days, a deposit is made for $1000 to maximum balance
        On day 11, a backdated deposit $5 is made with a value timestamp day 9

        Expectation:

        live balance:
        When processing the first 10 posting, the contract (pre_posting_code())
        sees the balance without hitting maximum balance and accepts the posting.
        Then when processing the backdated posting the contract sees the live balance
        of $10000 and rejects the posting as maximum balance is hit.
        """

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=26, hour=23, tzinfo=timezone.utc)

        instance_params = {
            **default_instance_params,
            "interest_application_day": "28",
        }
        template_params = {
            **default_template_params,
            "minimum_deposit": "5",
        }

        sub_tests = [
            SubTest(
                description="ensure the live balance is used",
                events=self._create_transactions_to_maximum_balance(start, 10)
                + [
                    # This should fail.
                    create_inbound_hard_settlement_instruction(
                        amount="5.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        value_timestamp=(start + timedelta(days=5, hours=1)),
                        event_datetime=(start + timedelta(days=11, hours=1)),
                    )
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(days=11, hours=1),
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Posting would cause the maximum balance to be exceeded.",
                    )
                ],
                expected_balances_at_ts={
                    end: {"Main account": [(BalanceDimensions(denomination="USD"), "10000.00")]}
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_close_code_reverses_accrued_interest(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=26, hour=23, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "0",
            "maximum_balance": "0",
        }
        instance_params = {
            **default_instance_params,
            "interest_application_day": "28",
        }

        before_account_closure = datetime(year=2019, month=1, day=25, tzinfo=timezone.utc)
        account_closure_time = before_account_closure + timedelta(hours=2)
        after_account_closure = before_account_closure + timedelta(hours=5)

        sub_tests = [
            SubTest(
                description="test balance update after a single deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        "20000", start + timedelta(hours=1), denomination="USD"
                    )
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(hours=1, minutes=1): {
                        "Main account": [(BalanceDimensions(denomination="USD"), "20000")]
                    }
                },
            ),
            SubTest(
                description="test balances after tiered interest accrual",
                expected_balances_at_ts={
                    start
                    + timedelta(days=1, hours=1): {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "20000"),
                            # tier1 daily interest accrual = 15000 * 0.149 / 365 = 6.12329
                            # tier2 daily interest accrual = 5000 * -0.1485 / 365 = 2.03425
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE", denomination="USD"
                                ),
                                "6.12329",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_RECEIVABLE", denomination="USD"
                                ),
                                "-2.03425",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-6.12329")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-2.03425")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    }
                },
            ),
            SubTest(
                description="test balances before closure",
                expected_balances_at_ts={
                    before_account_closure: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "20000"),
                            # tier1 interest accrual =  6.12329 * 24 = 146.95896
                            # tier2 interest accrual = 2.03425 * 24 = 48.8220
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE", denomination="USD"
                                ),
                                "146.95896",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_RECEIVABLE", denomination="USD"
                                ),
                                "-48.8220",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-146.95896")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-48.8220")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    }
                },
            ),
            SubTest(
                description="close account",
                events=[
                    update_account_status_pending_closure(
                        timestamp=account_closure_time, account_id="Main account"
                    )
                ],
                expected_balances_at_ts={
                    after_account_closure: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "20000"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE", denomination="USD"
                                ),
                                "0",
                            ),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_RECEIVABLE", denomination="USD"
                                ),
                                "0",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                        ACCRUED_INTEREST_RECEIVABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0")
                        ],
                        INTEREST_RECEIVED_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
                    }
                },
            ),
        ]
        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
            template_params=template_params,
        )

        self.run_test_scenario(test_scenario)

    def test_single_deposit(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=23, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="create a single deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="122.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=(start + timedelta(hours=1)),
                    )
                ],
                expected_balances_at_ts={
                    end: {"Main account": [(BalanceDimensions(denomination="USD"), "122.00")]}
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )

        self.run_test_scenario(test_scenario)

    def test_interest_accrual(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="create a single deposit and check accrual",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=(start + timedelta(hours=1)),
                    )
                ],
                expected_balances_at_ts={
                    end: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1000.00"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE", denomination="USD"
                                ),
                                "0.40822",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-0.40822")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
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

    def test_interest_accrual_no_balance_ranges(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, hour=10, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "balance_tier_ranges": json.dumps({"tier1": {"min": "0"}}),
            "tiered_interest_rates": json.dumps(
                {
                    "UPPER_TIER": {"tier1": "0.02"},
                    "MIDDLE_TIER": {"tier1": "0.0125"},
                    "LOWER_TIER": {"tier1": "0.1"},
                }
            ),
            "maximum_daily_deposit": "0",
            "maximum_balance": "0",
            "maximum_daily_withdrawal": "0",
        }

        sub_tests = [
            SubTest(
                description="create a deposit and withdrawal",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="20000.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=(start + timedelta(hours=1)),
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="15000.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=(start + timedelta(days=1, hours=4)),
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "5000.00"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE", denomination="USD"
                                ),
                                "5.47945",
                            ),
                            (BalanceDimensions(address="INTERNAL_CONTRA", denomination="USD"), "0"),
                        ],
                        ACCRUED_INTEREST_PAYABLE_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "-5.47945")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "0")],
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

    def test_interest_application(self):
        """Check interest is applied correctly"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=1, hour=1, tzinfo=timezone.utc)

        instance_params = {
            **default_instance_params,
            "interest_application_day": "1",
        }

        sub_tests = [
            SubTest(
                description="create a single deposit and check accrual application",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=(start + timedelta(hours=1)),
                    )
                ],
                expected_balances_at_ts={
                    end: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1024.22"),
                            (
                                BalanceDimensions(
                                    address="ACCRUED_INTEREST_PAYABLE",
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
                            (BalanceDimensions(denomination="USD"), "0.00")
                        ],
                        INTEREST_PAID_ACCOUNT: [(BalanceDimensions(denomination="USD"), "24.22")],
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, instance_params=instance_params
        )

        self.run_test_scenario(test_scenario)

    def test_deposit_scenarios(self):
        """Check deposits scenarios."""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=28, hour=1, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "1000",
            "maximum_daily_withdrawal": "1000",
        }
        instance_params = {
            **default_instance_params,
            "interest_application_day": "28",
        }

        first_day_deposit_1 = start + timedelta(hours=1)
        first_day_deposit_2 = start + timedelta(hours=2)

        second_day_deposit_1 = start + timedelta(days=1, hours=1)
        second_day_deposit_2 = start + timedelta(days=1, hours=2)

        third_day_deposit_1 = start + timedelta(days=2, hours=1)
        third_day_withdrawal_1 = start + timedelta(days=2, hours=2)
        third_day_deposit_2 = start + timedelta(days=2, hours=3)

        fourth_day_deposit_1 = start + timedelta(days=3, hours=1)
        fourth_day_deposit_2 = start + timedelta(days=3, hours=2)

        fifth_day = start + timedelta(days=4, hours=1)

        sixth_day = start + timedelta(days=5, hours=1)

        fifteenth_day = start + timedelta(days=14, hours=1)

        end_of_month = start + timedelta(days=27, hours=1)

        sub_tests = [
            SubTest(
                description="check max deposit limits are respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1001.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=first_day_deposit_1,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="1000.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=first_day_deposit_2,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=first_day_deposit_1,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction would cause the maximum daily deposit limit of 1000 USD "
                            "to be exceeded."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    first_day_deposit_2: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1000.00"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check max daily deposit over multiple postings, and at the same time",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="500.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=second_day_deposit_1,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="600.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=second_day_deposit_1,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="1000.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=second_day_deposit_2,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=second_day_deposit_1,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction would cause the maximum daily deposit limit of 1000 USD to"
                            " be exceeded."
                        ),
                    ),
                    ExpectedRejection(
                        timestamp=second_day_deposit_2,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction would cause the maximum daily deposit limit of 1000 USD to"
                            " be exceeded."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    second_day_deposit_2: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1500.00"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check withdrawals do not affect daily deposit limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=third_day_deposit_1,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="600.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=third_day_withdrawal_1,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="300.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=third_day_deposit_2,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=third_day_deposit_2,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction would cause the maximum daily deposit limit of 1000 USD to"
                            " be exceeded."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    third_day_deposit_2: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1900.00"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check minimum deposit limits are respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="99.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=fourth_day_deposit_1,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="0.01",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=fourth_day_deposit_2,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=fourth_day_deposit_1,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount is less than the minimum deposit amount 100 USD."
                        ),
                    ),
                    ExpectedRejection(
                        timestamp=fourth_day_deposit_2,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount is less than the minimum deposit amount 100 USD."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    fourth_day_deposit_2: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1900.00"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check max balance limits are respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=fifth_day,
                    ),
                ]
                + self._create_transactions_to_maximum_balance(sixth_day, 8)
                + [
                    create_inbound_hard_settlement_instruction(
                        amount="500.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=fifteenth_day,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=fifteenth_day,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Posting would cause the maximum balance to be exceeded.",
                    )
                ],
                expected_balances_at_ts={
                    fifteenth_day: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "10000.00"),
                        ],
                    }
                },
            ),
            SubTest(
                description=(
                    "check accruals are still applied at max deposit amount, and deposits are "
                    "still rejected"
                ),
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=end_of_month,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=end_of_month,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Posting would cause the maximum balance to be exceeded.",
                    )
                ],
                expected_balances_at_ts={
                    end_of_month: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "10081.77"),
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

    def test_withdrawal_scenarios(self):
        """Check withdrawal scenarios."""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=5, hour=23, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "maximum_daily_deposit": "1000",
            "maximum_daily_withdrawal": "100",
            "minimum_withdrawal": "5",
            "tiered_interest_rates": ZERO_TIERED_INTEREST_RATES,
        }
        instance_params = {
            **default_instance_params,
            "interest_application_day": "28",
        }

        first_day_deposit_1 = start + timedelta(hours=1)
        first_day_withdrawal_1 = start + timedelta(hours=2)
        first_day_withdrawal_2 = start + timedelta(hours=3)

        second_day_withdrawal_1 = start + timedelta(days=1, hours=1)
        second_day_withdrawal_2 = start + timedelta(days=1, hours=2)
        second_day_withdrawal_3 = start + timedelta(days=1, hours=3)

        third_day_withdrawal_1 = start + timedelta(days=2, hours=1)
        third_day_deposit_1 = start + timedelta(days=2, hours=2)
        third_day_withdrawal_2 = start + timedelta(days=2, hours=3)

        fourth_day_withdrawal_1 = start + timedelta(days=3, hours=1)
        fourth_day_withdrawal_2 = start + timedelta(days=3, hours=2)

        fifth_day_withdrawal_1 = start + timedelta(days=4, hours=1)
        fifth_day_withdrawal_2 = start + timedelta(days=4, hours=2)

        sub_tests = [
            SubTest(
                description="check max withdrawal limits are respected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=first_day_deposit_1,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="1000.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=first_day_withdrawal_1,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=first_day_withdrawal_2,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=first_day_withdrawal_1,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction would cause the maximum daily withdrawal limit of 100 USD "
                            "to be exceeded."
                        ),
                    )
                ],
                expected_balances_at_ts={
                    first_day_withdrawal_2: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "900.00"),
                        ],
                    }
                },
            ),
            SubTest(
                description=(
                    "check min withdrawal limits are respected, along with multiple withdrawals on"
                    " a single day"
                ),
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="0.01",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=second_day_withdrawal_1,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="5.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=second_day_withdrawal_2,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="95.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=second_day_withdrawal_3,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=second_day_withdrawal_1,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction amount is less than the minimum withdrawal amount 5 USD."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    second_day_withdrawal_3: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "800.00"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check deposits do not affect daily withdrawal limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="100.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=third_day_withdrawal_1,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="200.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=third_day_deposit_1,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=third_day_withdrawal_2,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=third_day_withdrawal_2,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason=(
                            "Transaction would cause the maximum daily withdrawal limit of 100 USD"
                            " to be exceeded."
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    third_day_withdrawal_2: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "900.00"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check monthly withdrawal limit respected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="10.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=fourth_day_withdrawal_1,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="10.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=fourth_day_withdrawal_2,
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=fourth_day_withdrawal_2,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Exceeding monthly allowed withdrawal number: 5",
                    ),
                ],
                expected_balances_at_ts={
                    fourth_day_withdrawal_2: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "890.00"),
                        ],
                    }
                },
            ),
            SubTest(
                description="check monthly withdrawal limit fee applied",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=4),
                        reject_excess_withdrawals="false",
                    ),
                    # Withdrawal fee of 10.00
                    create_outbound_hard_settlement_instruction(
                        amount="10.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=fifth_day_withdrawal_1,
                    ),
                    # Ensure a batch applies a withdrawal fee for each entry
                    create_posting_instruction_batch(
                        instructions=[
                            OutboundHardSettlement(
                                target_account_id="Main account",
                                denomination="USD",
                                internal_account_id="1",
                                amount="10.00",
                            ),
                            OutboundHardSettlement(
                                target_account_id="Main account",
                                denomination="USD",
                                internal_account_id="1",
                                amount="10.00",
                            ),
                        ],
                        event_datetime=fifth_day_withdrawal_2,
                    ),
                ],
                expected_balances_at_ts={
                    fifth_day_withdrawal_2: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "830.00"),
                        ],
                        EXCESS_WITHDRAWAL_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "30.00")
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

    def test_denominations(self):
        """Ensure incorrect denominations are rejected"""
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=2, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="check incorrect denomination is rejected",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="1000.00",
                        denomination="SGD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=(start + timedelta(hours=1)),
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="1000.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=(start + timedelta(hours=1)),
                    ),
                ],
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start + timedelta(hour=1),
                        rejection_type="WrongDenomination",
                        rejection_reason=(
                            "Cannot make transactions in given denomination; "
                            "transactions must be in USD"
                        ),
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1000.00"),
                            (BalanceDimensions(denomination="SGD"), "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests
        )

        self.run_test_scenario(test_scenario)

    def test_schedules(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=7, hour=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "fees_application_day": "3",
            "fees_application_hour": "4",
            "fees_application_minute": "5",
            "fees_application_second": "6",
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
        apply_interest_schedule_before_change = self._create_list_of_schedule_datetimes(
            start=datetime(
                year=2019,
                month=1,
                day=5,
                hour=0,
                minute=1,
                second=0,
                tzinfo=timezone.utc,
            ),
            end=start + timedelta(months=6, hours=2),
            frequency="monthly",
        )
        # Only 1 interest application per month
        apply_interest_schedule_after_change = self._create_list_of_schedule_datetimes(
            start=datetime(
                year=2019,
                month=7,
                day=15,
                hour=0,
                minute=1,
                second=0,
                tzinfo=timezone.utc,
            ),
            end=end,
            frequency="monthly",
        )
        apply_monthly_fees_datetime = self._create_list_of_schedule_datetimes(
            start=datetime(
                year=2019,
                month=2,
                day=3,
                hour=4,
                minute=5,
                second=6,
                tzinfo=timezone.utc,
            ),
            end=end,
            frequency="monthly",
        )

        sub_tests = [
            SubTest(
                description="check schedules are created as expected",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + timedelta(months=6, hours=2),
                        account_id="Main account",
                        interest_application_day="15",
                    )
                ],
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=accrue_interest_schedule,
                        count=len(accrue_interest_schedule),
                        event_id="ACCRUE_INTEREST",
                        account_id="Main account",
                    ),
                    ExpectedSchedule(
                        run_times=apply_interest_schedule_before_change,
                        count=len(
                            apply_interest_schedule_before_change
                            + apply_interest_schedule_after_change
                        ),
                        event_id="APPLY_ACCRUED_INTEREST",
                        account_id="Main account",
                    ),
                    ExpectedSchedule(
                        run_times=apply_interest_schedule_after_change,
                        count=len(
                            apply_interest_schedule_before_change
                            + apply_interest_schedule_after_change
                        ),
                        event_id="APPLY_ACCRUED_INTEREST",
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

    def test_schedules_when_lt_period_from_creation(self):
        """
        test_get_next_apply_fees_schedule_correct_monthly_schedule_when_lt_period_fr_creation
        test_get_next_apply_fees_schedule_correct_yearly_schedule_when_lt_period_fr_creation
        """
        start = datetime(year=2020, month=1, day=2, tzinfo=timezone.utc)
        end = datetime(year=2021, month=2, day=1, hour=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "fees_application_day": "1",
            "fees_application_hour": "0",
            "fees_application_minute": "1",
            "fees_application_second": "0",
        }

        apply_monthly_fees_datetime_when_lt_period_fr_creation = (
            self._create_list_of_schedule_datetimes(
                start=datetime(
                    year=2020,
                    month=3,
                    day=1,
                    hour=0,
                    minute=1,
                    second=0,
                    tzinfo=timezone.utc,
                ),
                end=end,
                frequency="monthly",
            )
        )

        sub_tests = [
            SubTest(
                description="check schedules are created as expected",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=apply_monthly_fees_datetime_when_lt_period_fr_creation,
                        count=len(apply_monthly_fees_datetime_when_lt_period_fr_creation),
                        event_id="APPLY_MONTHLY_FEES",
                        account_id="Main account",
                    ),
                ],
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start, end=end, sub_tests=sub_tests, template_params=template_params
        )

        self.run_test_scenario(test_scenario)

    def test_schedules_with_changing_interest_application_frequency(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=2, day=7, hour=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "interest_application_frequency": "quarterly",
        }
        instance_params = {
            **default_instance_params,
            "interest_application_day": "28",
        }

        quarterly_interest_applications = self._create_list_of_schedule_datetimes(
            start=datetime(
                year=2019,
                month=4,
                day=28,
                hour=0,
                minute=1,
                second=0,
                tzinfo=timezone.utc,
            ),
            end=end,
            frequency="quarterly",
        )

        sub_tests = [
            SubTest(
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(months=6, hours=2),
                        interest_application_frequency="annually",
                    ),
                ],
                description="check quarterly schedules are not updated after parameter change",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=quarterly_interest_applications,
                        count=len(quarterly_interest_applications),
                        event_id="APPLY_ACCRUED_INTEREST",
                        account_id="Main account",
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

    def test_schedules_with_invalid_day_defaults_to_last_day_of_month(self):
        start = datetime(year=2019, month=2, day=2, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=1, tzinfo=timezone.utc)

        instance_params = {
            **default_instance_params,
            "interest_application_day": "31",
        }

        monthly_interest_applications = self._create_list_of_schedule_datetimes(
            start=datetime(
                year=2019,
                month=2,
                day=28,
                hour=0,
                minute=1,
                second=0,
                tzinfo=timezone.utc,
            ),
            end=end,
            frequency="monthly",
        )

        sub_tests = [
            SubTest(
                description="check application schedules default to end of month",
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=monthly_interest_applications,
                        count=len(monthly_interest_applications),
                        event_id="APPLY_ACCRUED_INTEREST",
                        account_id="Main account",
                    ),
                ],
            )
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )

        self.run_test_scenario(test_scenario)

    def test_minimum_average_balance(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=3, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "interest_application_frequency": "quarterly",
            "minimum_balance_fee": "10",
            "tiered_interest_rates": ZERO_TIERED_INTEREST_RATES,
            "fees_application_hour": "23",
            "fees_application_minute": "59",
            "fees_application_second": "59",
            "maximum_daily_withdrawal": "1000",
            "minimum_deposit": "50",
        }

        jan_deposit_1 = start + timedelta(hours=1)
        jan_deposit_2 = start + timedelta(days=30, hours=23, minute=59)
        feb_withdrawal_1 = start + timedelta(months=1, seconds=1)
        jan_fee_check = start + timedelta(months=1, days=1)

        feb_deposit_1 = start + timedelta(months=1, hours=23)
        feb_withdrawal_2 = start + timedelta(months=1, days=1, hours=23)
        feb_fee_check = start + timedelta(months=2, days=1)

        sub_tests = [
            SubTest(
                description="check minimum average balance midnight sampling works",
                events=[
                    # [(99 * 30) + 199]/31 = 102.23
                    create_inbound_hard_settlement_instruction(
                        amount="99.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=jan_deposit_1,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=jan_deposit_2,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="100.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=feb_withdrawal_1,
                    ),
                ],
                expected_balances_at_ts={
                    jan_fee_check: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "1000.00"),
                        ],
                        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00")
                        ],
                    }
                },
            ),
            SubTest(
                description="check minimum average balance over february works, and MAB is applied",
                # [99 + 1000 + (65*26)] / 28 = 99.607
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="901.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=feb_deposit_1,
                    ),
                    create_outbound_hard_settlement_instruction(
                        amount="935.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=feb_withdrawal_2,
                    ),
                ],
                expected_balances_at_ts={
                    feb_fee_check: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "55.00"),
                        ],
                        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "10.00")
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

    def test_minimum_average_balance_flag_tiers(self):
        """
        Test minimum balances and their interactions with flags.
        No flags are tested in other tests.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=2, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "minimum_balance_fee": "10",
            "account_tier_names": json.dumps(["X", "Y", "Z"]),
            "tiered_minimum_balance_threshold": json.dumps({"X": "10", "Y": "100", "Z": "200"}),
            "tiered_interest_rates": json.dumps(
                {
                    "X": {"tier1": "0", "tier2": "0"},
                    "Y": {"tier1": "0", "tier2": "0"},
                    "Z": {"tier1": "0", "tier2": "0"},
                }
            ),
            "maintenance_fee_monthly": json.dumps({"X": "0", "Y": "0", "Z": "0"}),
        }

        jan_deposit_1 = start + timedelta(hours=1)
        jan_fee_check = start + timedelta(months=1, days=1)

        feb_withdrawal_1 = start + timedelta(months=1, days=1, hours=1)
        feb_fee_check = start + timedelta(months=2, days=1)

        sub_tests = [
            SubTest(
                description="check lower tier min balance is used.",
                events=[
                    create_flag_definition_event(timestamp=start, flag_definition_id="X"),
                    create_flag_definition_event(timestamp=start, flag_definition_id="Y"),
                    create_flag_event(
                        timestamp=start,
                        flag_definition_id="X",
                        account_id="Main account",
                        expiry_timestamp=start + timedelta(months=1, days=4),
                    ),
                    create_flag_event(
                        timestamp=start,
                        flag_definition_id="Y",
                        account_id="Main account",
                        expiry_timestamp=end,
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="100.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=jan_deposit_1,
                    ),
                ],
                expected_balances_at_ts={
                    jan_fee_check: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "100.00"),
                        ],
                        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "0.00")
                        ],
                    }
                },
            ),
            SubTest(
                description="check expired flags don't affect tier in use.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        amount="50.00",
                        denomination="USD",
                        target_account_id="Main account",
                        internal_account_id="1",
                        event_datetime=feb_withdrawal_1,
                    ),
                ],
                expected_balances_at_ts={
                    feb_fee_check: {
                        "Main account": [
                            (BalanceDimensions(denomination="USD"), "40.00"),
                        ],
                        MINIMUM_BALANCE_FEE_INCOME_ACCOUNT: [
                            (BalanceDimensions(denomination="USD"), "10.00")
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

    def test_excess_withdrawal_limit(self):
        start = datetime(year=2020, month=1, day=10, tzinfo=timezone.utc)
        end = datetime(year=2020, month=1, day=17, tzinfo=timezone.utc)

        template_params = {
            **default_template_params,
            "reject_excess_withdrawals": "true",
            "excess_withdrawal_fee": "10",
            "monthly_withdrawal_limit": "3",
        }
        instance_params = {
            **default_instance_params,
            "interest_application_day": "5",
        }
        denomination = template_params["denomination"]

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
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + timedelta(days=1),
                        resource_id="Main account",
                        resource_type="RESOURCE_ACCOUNT",
                        notification_type="US_PRODUCTS_TRANSACTION_LIMIT_WARNING",
                        notification_details={
                            "account_id": "Main account",
                            "limit": "3",
                            "limit_type": "Monthly Withdrawal Limit",
                            "message": "Warning: Reached monthly withdrawal transaction limit, no "
                            "further withdrawals will be allowed for the current period.",
                            "value": "3",
                        },
                    ),
                ],
            ),
            SubTest(
                description="Limit increased and excess withdrawals allowed, so PIB with "
                "3 withdrawals (6 total, 1 excess) results in fee",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=1, hours=6),
                        smart_contract_version_id=self.contract_version_id,
                        monthly_withdrawal_limit="5",
                    ),
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=1, hours=7),
                        smart_contract_version_id=self.contract_version_id,
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
                expected_contract_notifications=[
                    ExpectedContractNotification(
                        timestamp=start + timedelta(days=2),
                        resource_id="Main account",
                        resource_type="RESOURCE_ACCOUNT",
                        notification_type="US_PRODUCTS_TRANSACTION_LIMIT_WARNING",
                        notification_details={
                            "account_id": "Main account",
                            "limit": "5",
                            "limit_type": "Monthly Withdrawal Limit",
                            "message": "Warning: Reached monthly withdrawal transaction limit, "
                            "charges will be applied for the next withdrawal.",
                            "value": "6",
                        },
                    ),
                ],
            ),
            SubTest(
                description="Set fees to 0 and make another excess withdrawal",
                events=[
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=2, hours=6),
                        smart_contract_version_id=self.contract_version_id,
                        excess_withdrawal_fee="0",
                    ),
                    # exceeds withdrawal limit with fee 0
                    create_outbound_hard_settlement_instruction(
                        amount="10",
                        denomination=denomination,
                        event_datetime=start + timedelta(days=3),
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
                        smart_contract_version_id=self.contract_version_id,
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
                        smart_contract_version_id=self.contract_version_id,
                        excess_withdrawal_fee="15",
                    ),
                    create_template_parameter_change_event(
                        timestamp=start + timedelta(days=5, hours=7),
                        smart_contract_version_id=self.contract_version_id,
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


if __name__ == "__main__":
    if any(item.startswith("test") for item in sys.argv):
        unittest.main(USSavingsAccountTest)
    else:
        unittest.main(USSavingsAccountTest())
