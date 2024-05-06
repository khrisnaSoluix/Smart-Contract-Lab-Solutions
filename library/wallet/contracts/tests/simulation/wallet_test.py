import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractModuleConfig,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
    get_balances,
    get_num_postings,
    get_postings,
    get_processed_scheduled_events,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_instruction,
    create_auth_adjustment_instruction,
    create_flag_definition_event,
    create_flag_event,
    create_outbound_authorisation_instruction,
    create_instance_parameter_change_event,
    create_inbound_hard_settlement_instruction,
    create_outbound_hard_settlement_instruction,
    create_release_event,
    create_settlement_event,
    create_transfer_instruction,
    update_account_status_pending_closure,
)
from typing import List, Dict

CONTRACT_FILE = "library/wallet/contracts/wallet.py"
CONTRACT_FILES = [CONTRACT_FILE]
CONTRACT_MODULES_ALIAS_FILE_MAP = {"utils": "library/common/contract_modules/utils.py"}

AUTO_TOP_UP_FLAG = "AUTO_TOP_UP_WALLET"
USD_DEFAULT_DIMENSIONS = BalanceDimensions(denomination="USD")
SGD_DEFAULT_DIMENSIONS = BalanceDimensions(denomination="SGD")
SGD_PENDING_OUT_DIMENSIONS = BalanceDimensions(
    denomination="SGD", phase="POSTING_PHASE_PENDING_OUTGOING"
)
SGD_TODAYS_SPENDING = BalanceDimensions(address="todays_spending", denomination="SGD")
WALLET_ACCOUNT = "wallet_account"

LIABILITY = "LIABILITY"
INTERNAL_ACCOUNT = "internal_account"

default_internal_accounts = {INTERNAL_ACCOUNT: LIABILITY}

default_instance_params = {
    "denomination": "SGD",
    "customer_wallet_limit": "1000",
    "nominated_account": "2",
    "daily_spending_limit": "9999",
    "additional_denominations": json.dumps(["GBP", "USD"]),
}

default_template_params = {
    "zero_out_daily_spend_hour": "23",
    "zero_out_daily_spend_minute": "59",
    "zero_out_daily_spend_second": "59",
}


class WalletTest(SimulationTestCase):
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
    ):
        contract_config = ContractConfig(
            contract_file_path=CONTRACT_FILE,
            template_params=template_params or default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or default_instance_params,
                    account_id_base=WALLET_ACCOUNT,
                )
            ],
            linked_contract_modules=self.contract_modules,
        )
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=internal_accounts or default_internal_accounts,
        )

    def default_create_account_instruction(self, start, instance_param_vals=None):
        return create_account_instruction(
            timestamp=start,
            account_id="wallet_account",
            product_id="1000",
            instance_param_vals=instance_param_vals or default_instance_params,
        )

    def run_test(
        self,
        start: datetime,
        end: datetime,
        events: List,
        template_params: Dict[str, str] = None,
        instance_params: Dict[str, str] = None,
    ):
        contract_config = ContractConfig(
            contract_file_path=CONTRACT_FILE,
            smart_contract_version_id="1000",
            template_params=template_params or default_instance_params,
            account_configs=[
                AccountConfig(instance_params=instance_params or default_instance_params)
            ],
            linked_contract_modules=self.contract_modules,
        )
        return self.client.simulate_smart_contract(
            contract_codes=self.smart_contract_contents.copy(),
            contract_config=contract_config,
            smart_contract_version_ids=["1000"],
            start_timestamp=start,
            end_timestamp=end,
            templates_parameters=[
                template_params or default_template_params,
                {},
                {},
            ],
            internal_account_ids=["1", "2"],
            events=events,
        )

    def test_change_customer_limit_no_balance_no_sweep(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_instance_parameter_change_event(
                timestamp=start,
                account_id="wallet_account",
                customer_wallet_limit="500",
            ),
        ]

        res = self.run_test(start, end, events)

        self.assertEqual(get_num_postings(res, "wallet_account"), 0)

    def test_change_customer_limit_balance_no_sweep(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="450",
                event_datetime=start,
                denomination="SGD",
            ),
            create_instance_parameter_change_event(
                timestamp=start + timedelta(minutes=1),
                account_id="wallet_account",
                customer_wallet_limit="500",
            ),
        ]

        res = self.run_test(start, end, events)

        self.assertEqual(get_num_postings(res, "wallet_account"), 1)

    def test_change_customer_limit_balance_sweep(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="1000",
                event_datetime=start,
                denomination="SGD",
            ),
            create_instance_parameter_change_event(
                timestamp=start + timedelta(minutes=1),
                account_id="wallet_account",
                customer_wallet_limit="500",
            ),
        ]

        res = self.run_test(start, end, events)

        postings = get_postings(res, "wallet_account")
        self.assertEqual(len(postings), 2)
        debit_postings = [posting for posting in postings if not posting["credit"]]
        self.assertEqual(len(debit_postings), 1)
        self.assertEqual(Decimal(debit_postings[0]["amount"]), Decimal("500.0"))

    def test_multiple_balance_sweeps_same_day(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="1000",
                event_datetime=start,
                denomination="SGD",
            ),
            create_instance_parameter_change_event(
                timestamp=start + timedelta(minutes=1),
                account_id="wallet_account",
                customer_wallet_limit="800",
            ),
            create_instance_parameter_change_event(
                timestamp=start + timedelta(minutes=2),
                account_id="wallet_account",
                customer_wallet_limit="500",
            ),
            create_instance_parameter_change_event(
                timestamp=start + timedelta(minutes=3),
                account_id="wallet_account",
                customer_wallet_limit="600",
            ),
        ]

        res = self.run_test(start, end, events)

        postings = get_postings(res, "wallet_account")
        self.assertEqual(len(postings), 3)
        debit_postings = [posting for posting in postings if not posting["credit"]]
        self.assertEqual(len(debit_postings), 2)
        self.assertEqual(Decimal(debit_postings[0]["amount"]), Decimal("200.0"))
        self.assertEqual(Decimal(debit_postings[1]["amount"]), Decimal("300.0"))

    def test_multiple_balance_sweeps_different_day(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=5, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="1000",
                event_datetime=start,
                denomination="SGD",
            ),
            create_instance_parameter_change_event(
                timestamp=start + timedelta(days=1),
                account_id="wallet_account",
                customer_wallet_limit="800",
            ),
            create_instance_parameter_change_event(
                timestamp=start + timedelta(days=2),
                account_id="wallet_account",
                customer_wallet_limit="500",
            ),
            create_instance_parameter_change_event(
                timestamp=start + timedelta(days=3),
                account_id="wallet_account",
                customer_wallet_limit="600",
            ),
        ]

        res = self.run_test(start, end, events)

        # The last limit change should not result in a sweep
        postings = get_postings(res, "wallet_account")
        self.assertEqual(len(postings), 3)
        debit_postings = [posting for posting in postings if not posting["credit"]]
        self.assertEqual(len(debit_postings), 2)
        self.assertEqual(Decimal(debit_postings[0]["amount"]), Decimal("200.0"))
        self.assertEqual(Decimal(debit_postings[1]["amount"]), Decimal("300.0"))

    def test_multiple_param_changes_same_day_no_sweep(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="1000",
                event_datetime=start,
                denomination="SGD",
            ),
            create_instance_parameter_change_event(
                timestamp=start + timedelta(minutes=1),
                account_id="wallet_account",
                customer_wallet_limit="1200",
            ),
            create_instance_parameter_change_event(
                timestamp=start + timedelta(minutes=2),
                account_id="wallet_account",
                customer_wallet_limit="1500",
            ),
            create_instance_parameter_change_event(
                timestamp=start + timedelta(minutes=3),
                account_id="wallet_account",
                customer_wallet_limit="2000",
            ),
            create_instance_parameter_change_event(
                timestamp=start + timedelta(minutes=3),
                account_id="wallet_account",
                nominated_account="Some Other Account",
            ),
        ]

        res = self.run_test(start, end, events)

        self.assertEqual(get_num_postings(res, "wallet_account"), 1)

    def test_spending_is_mirrored(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="50",
                event_datetime=start,
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="50",
                event_datetime=start + timedelta(minutes=1),
                denomination="SGD",
            ),
        ]

        res = self.run_test(start, end, events)
        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_TODAYS_SPENDING, "-50")]}},
        )

    def test_spending_is_mirrored_for_secondary_instructions(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=5, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="1000",
                event_datetime=start,
                denomination="SGD",
            ),
            create_outbound_authorisation_instruction(
                target_account_id="wallet_account",
                amount="500",
                event_datetime=start + timedelta(hours=1),
                denomination="SGD",
                client_transaction_id="A",
            ),
            # The auth adjust is reduced, which should decrease today's spending
            create_auth_adjustment_instruction(
                amount="-100",
                client_transaction_id="A",
                event_datetime=start + timedelta(hours=2),
            ),
            # The increase should increase today's spending
            create_auth_adjustment_instruction(
                amount="100",
                client_transaction_id="A",
                event_datetime=start + timedelta(hours=3),
            ),
            # Partial settle should
            # permanently increase today's spending (until reset at EOD)
            create_settlement_event(
                client_transaction_id="A",
                amount="100",
                final=False,
                event_datetime=start + timedelta(hours=4),
            ),
            # The release should clear today's spending
            create_release_event(
                client_transaction_id="A",
                event_datetime=start + timedelta(hours=5),
            ),
        ]

        res = self.run_test(start, end, events)
        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "wallet_account": {
                    start
                    + timedelta(hours=1): [
                        (SGD_TODAYS_SPENDING, "-500"),
                        (SGD_DEFAULT_DIMENSIONS, "1000"),
                        (SGD_PENDING_OUT_DIMENSIONS, "-500"),
                    ],
                    start
                    + timedelta(hours=2): [
                        (SGD_TODAYS_SPENDING, "-400"),
                        (SGD_DEFAULT_DIMENSIONS, "1000"),
                        (SGD_PENDING_OUT_DIMENSIONS, "-400"),
                    ],
                    start
                    + timedelta(hours=3): [
                        (SGD_TODAYS_SPENDING, "-500"),
                        (SGD_DEFAULT_DIMENSIONS, "1000"),
                        (SGD_PENDING_OUT_DIMENSIONS, "-500"),
                    ],
                    start
                    + timedelta(hours=4): [
                        (SGD_TODAYS_SPENDING, "-500"),
                        (SGD_DEFAULT_DIMENSIONS, "900"),
                        (SGD_PENDING_OUT_DIMENSIONS, "-400"),
                    ],
                    start
                    + timedelta(hours=5): [
                        (SGD_TODAYS_SPENDING, "-100"),
                        (SGD_DEFAULT_DIMENSIONS, "900"),
                        (SGD_PENDING_OUT_DIMENSIONS, "0"),
                    ],
                }
            },
        )

    def test_spending_is_mirrored_multiple_postings(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="100",
                event_datetime=start,
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="40",
                event_datetime=start + timedelta(minutes=1),
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="60",
                event_datetime=start + timedelta(minutes=2),
                denomination="SGD",
            ),
        ]

        res = self.run_test(start, end, events)
        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_TODAYS_SPENDING, "-100")]}},
        )

    def test_spending_is_zeroed_out_at_midnight(self):
        """
        Test that the correct schedules to zero out daily spend are
        created when the account is instantiated and the todays spending
        is zeroed out.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        template_params = default_template_params.copy()

        posting_date = start + timedelta(minutes=1)
        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="50",
                event_datetime=start,
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="50",
                event_datetime=posting_date,
                denomination="SGD",
            ),
        ]

        res = self.run_test(start, end, events)

        zero_out_daily_spend_event = get_processed_scheduled_events(
            res, event_id="ZERO_OUT_DAILY_SPEND", account_id="wallet_account"
        )

        self.assertEqual(len(zero_out_daily_spend_event), 1)
        date = datetime.fromisoformat(zero_out_daily_spend_event[0][:-1])
        self.assertEqual(date.hour, int(template_params["zero_out_daily_spend_hour"]))
        self.assertEqual(date.minute, int(template_params["zero_out_daily_spend_minute"]))
        self.assertEqual(date.second, int(template_params["zero_out_daily_spend_second"]))

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "wallet_account": {
                    posting_date: [(SGD_TODAYS_SPENDING, "-50")],
                    end: [(SGD_TODAYS_SPENDING, "-0")],
                }
            },
        )

    def test_spending_is_zeroed_out_at_updated_params_value(self):
        """
        Test that the correct schedules to zero out daily spend are
        created when the account is instantiated with a change in
        default schedule parameter values and the todays spending
        is zeroed out.
        """
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        template_params = default_template_params.copy()
        template_params["zero_out_daily_spend_hour"] = "0"
        template_params["zero_out_daily_spend_minute"] = "0"
        template_params["zero_out_daily_spend_second"] = "0"

        posting_date = start + timedelta(minutes=1)
        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="50",
                event_datetime=start,
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="50",
                event_datetime=posting_date,
                denomination="SGD",
            ),
        ]

        res = self.run_test(start, end, events, template_params=template_params)

        zero_out_daily_spend_event = get_processed_scheduled_events(
            res, event_id="ZERO_OUT_DAILY_SPEND", account_id="wallet_account"
        )

        self.assertEqual(len(zero_out_daily_spend_event), 2)
        date = datetime.fromisoformat(zero_out_daily_spend_event[0][:-1])
        self.assertEqual(date.hour, int(template_params["zero_out_daily_spend_hour"]))
        self.assertEqual(date.minute, int(template_params["zero_out_daily_spend_minute"]))
        self.assertEqual(date.second, int(template_params["zero_out_daily_spend_second"]))

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "wallet_account": {
                    posting_date: [(SGD_TODAYS_SPENDING, "-50")],
                    end: [(SGD_TODAYS_SPENDING, "-0")],
                }
            },
        )

    def test_postings_above_limit_are_rejected(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        instance_parameters = default_instance_params.copy()
        instance_parameters["daily_spending_limit"] = "400"

        events = [
            self.default_create_account_instruction(start, instance_parameters),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="500",
                event_datetime=start,
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="450",
                event_datetime=start + timedelta(minutes=1),
                denomination="SGD",
            ),
        ]

        res = self.run_test(start, end, events, instance_params=instance_parameters)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_DEFAULT_DIMENSIONS, "500")]}},
        )

    def test_postings_above_limit_are_rejected_multiple_postings(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        instance_parameters = default_instance_params.copy()
        instance_parameters["daily_spending_limit"] = "400"

        events = [
            self.default_create_account_instruction(start, instance_parameters),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="500",
                event_datetime=start,
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="200",
                event_datetime=start + timedelta(minutes=1),
                denomination="SGD",
            ),
            create_outbound_authorisation_instruction(
                target_account_id="wallet_account",
                amount="200",
                event_datetime=start + timedelta(minutes=2),
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="50",
                event_datetime=start + timedelta(minutes=3),
                denomination="SGD",
            ),
            create_outbound_authorisation_instruction(
                target_account_id="wallet_account",
                amount="50",
                event_datetime=start + timedelta(minutes=4),
                denomination="SGD",
            ),
        ]

        res = self.run_test(start, end, events, instance_params=instance_parameters)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "wallet_account": {
                    end: [
                        (SGD_DEFAULT_DIMENSIONS, "300"),
                        (SGD_PENDING_OUT_DIMENSIONS, "-200"),
                    ]
                }
            },
        )

    def test_balance_cannot_go_above_limit_swept_out(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_transfer_instruction(
                creditor_target_account_id="wallet_account",
                debtor_target_account_id="1",
                amount="9999",
                event_datetime=start,
                denomination="SGD",
            ),
        ]

        res = self.run_test(start, end, events)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_DEFAULT_DIMENSIONS, "1000")]}},
        )

    def test_topped_up_balance_due_to_auth_is_swept_after_auth_adjust_and_release(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=4, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_flag_definition_event(timestamp=start, flag_definition_id=AUTO_TOP_UP_FLAG),
            create_flag_event(
                timestamp=start,
                flag_definition_id=AUTO_TOP_UP_FLAG,
                account_id="wallet_account",
                expiry_timestamp=end,
            ),
            create_outbound_authorisation_instruction(
                target_account_id="wallet_account",
                amount="1500",
                event_datetime=start,
                denomination="SGD",
                client_transaction_id="A",
            ),
            # The auth adjust is reduced such that the
            # previous top-up now pushes the account over
            # the wallet limit, which should trigger sweep
            create_auth_adjustment_instruction(
                amount="-1100",
                client_transaction_id="A",
                event_datetime=start + timedelta(hours=1),
            ),
            create_auth_adjustment_instruction(
                amount="1000",
                client_transaction_id="A",
                event_datetime=start + timedelta(hours=2),
            ),
            # The release should have a similar effect to the negative auth adjust
            create_release_event(
                client_transaction_id="A", event_datetime=start + timedelta(hours=3)
            ),
        ]

        res = self.run_test(start, end, events)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                start: {
                    "wallet_account": [
                        (SGD_TODAYS_SPENDING, "-1500"),
                        (SGD_DEFAULT_DIMENSIONS, "1500"),
                        (SGD_PENDING_OUT_DIMENSIONS, "-1500"),
                    ],
                    "2": [(SGD_DEFAULT_DIMENSIONS, "-1500")],
                },
                # 100 is swept back to nominated account to avoid exceeding the limit
                start
                + timedelta(hours=1): {
                    "wallet_account": [
                        (SGD_TODAYS_SPENDING, "-400"),
                        (SGD_DEFAULT_DIMENSIONS, "1400"),
                        (SGD_PENDING_OUT_DIMENSIONS, "-400"),
                    ],
                    "2": [(SGD_DEFAULT_DIMENSIONS, "-1400")],
                },
                start
                + timedelta(hours=2): {
                    "wallet_account": [
                        (SGD_TODAYS_SPENDING, "-1400"),
                        (SGD_DEFAULT_DIMENSIONS, "1400"),
                        (SGD_PENDING_OUT_DIMENSIONS, "-1400"),
                    ],
                    "2": [(SGD_DEFAULT_DIMENSIONS, "-1400")],
                },
                # 400 is swept back to nominated account to avoid exceeding the limit
                # spending balance is reduced as the batch is a refund
                start
                + timedelta(hours=3): {
                    "wallet_account": [
                        (SGD_TODAYS_SPENDING, "0"),
                        (SGD_DEFAULT_DIMENSIONS, "1000"),
                        (SGD_PENDING_OUT_DIMENSIONS, "0"),
                    ],
                    "2": [(SGD_DEFAULT_DIMENSIONS, "-1000")],
                },
            },
        )

    def test_postings_above_limit_are_not_rejected_with_refund(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        instance_parameters = default_instance_params.copy()
        instance_parameters["daily_spending_limit"] = "400"

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="500",
                event_datetime=start,
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="400",
                event_datetime=start + timedelta(minutes=1),
                denomination="SGD",
            ),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="400",
                event_datetime=start + timedelta(minutes=2),
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="400",
                event_datetime=start + timedelta(minutes=3),
                denomination="SGD",
            ),
        ]

        res = self.run_test(start, end, events)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_DEFAULT_DIMENSIONS, "100")]}},
        )

    def test_postings_above_limit_are_rejected_with_non_refund(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        instance_parameters = default_instance_params.copy()
        instance_parameters["daily_spending_limit"] = "400"

        events = [
            self.default_create_account_instruction(start, instance_parameters),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="500",
                event_datetime=start,
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="400",
                event_datetime=start + timedelta(minutes=1),
                denomination="SGD",
            ),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="400",
                event_datetime=start + timedelta(minutes=2),
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="400",
                event_datetime=start + timedelta(minutes=3),
                denomination="SGD",
            ),
        ]

        res = self.run_test(start, end, events, instance_params=instance_parameters)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_DEFAULT_DIMENSIONS, "500")]}},
        )

        self.assertEqual(get_num_postings(res, "wallet_account"), 3)

    def test_additional_denom_can_be_spent_not_exceeded(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=3, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="1000",
                event_datetime=start + timedelta(hours=1),
                denomination="GBP",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="200",
                event_datetime=start + timedelta(hours=1),
                denomination="GBP",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="900",
                event_datetime=start + timedelta(hours=1),
                denomination="GBP",
            ),
        ]

        res = self.run_test(start, end, events)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "wallet_account": {end: [(BalanceDimensions(denomination="GBP"), "800")]}
            },
        )

    def test_posting_rejected_if_flag_false_main_denom(self):
        """Ensure the balance stays zero with false flag"""

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=3, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="200",
                event_datetime=start + timedelta(hours=1),
                denomination="SGD",
            ),
        ]

        res = self.run_test(start, end, events)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_DEFAULT_DIMENSIONS, "0")]}},
        )

    def test_posting_rejected_if_unsupported_denom(self):
        """Ensure the balance stays zero with false flag"""

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=3, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="10",
                event_datetime=start + timedelta(hours=1),
                denomination="HKD",
            ),
        ]

        res = self.run_test(start, end, events)
        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "wallet_account": {
                    end: [
                        (SGD_DEFAULT_DIMENSIONS, "0"),
                        (BalanceDimensions(denomination="HKD"), "0"),
                    ]
                }
            },
        )

    def test_auto_top_up_triggered_when_flag_is_set(self):

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=3, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_flag_definition_event(timestamp=start, flag_definition_id=AUTO_TOP_UP_FLAG),
            create_flag_event(
                timestamp=start,
                flag_definition_id=AUTO_TOP_UP_FLAG,
                account_id="wallet_account",
                expiry_timestamp=end,
            ),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="10",
                event_datetime=start + timedelta(hours=1),
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="200",
                event_datetime=start + timedelta(hours=2),
                denomination="SGD",
            ),
        ]

        res = self.run_test(start, end, events)

        self.assertEqual(get_num_postings(res, "wallet_account"), 3)
        self.assertEqual(
            get_num_postings(res, "wallet_account", BalanceDimensions("todays_spending")),
            1,
        )
        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "wallet_account": {
                    end: [(SGD_TODAYS_SPENDING, "-200"), (SGD_DEFAULT_DIMENSIONS, "0")]
                },
                "2": {end: [(SGD_DEFAULT_DIMENSIONS, "-190")]},
            },
        )

    def test_auto_top_up_triggered_when_flag_is_set_for_auth_and_settle(self):

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=6, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_flag_definition_event(timestamp=start, flag_definition_id=AUTO_TOP_UP_FLAG),
            create_flag_event(
                timestamp=start,
                flag_definition_id=AUTO_TOP_UP_FLAG,
                account_id="wallet_account",
                expiry_timestamp=end,
            ),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="10",
                event_datetime=start + timedelta(hours=1),
                denomination="SGD",
            ),
            # We expect authorisations to behave equally to hard settlements
            # as they affect available balance
            create_outbound_authorisation_instruction(
                target_account_id="wallet_account",
                amount="100",
                event_datetime=start + timedelta(hours=2),
                denomination="SGD",
                client_transaction_id="A",
            ),
            # Auth adjust behaves as an additional auth
            create_auth_adjustment_instruction(
                amount="10",
                client_transaction_id="A",
                event_datetime=start + timedelta(hours=3),
            ),
            # Settlements have no impact as there is no change to available balance
            create_settlement_event(
                amount="100",
                event_datetime=start + timedelta(hours=4),
                client_transaction_id="A",
            ),
            # Over settling triggers more top-up
            create_settlement_event(
                amount="20",
                event_datetime=start + timedelta(hours=5),
                client_transaction_id="A",
                final=True,
            ),
        ]

        res = self.run_test(start, end, events)

        self.check_balances_by_ts(
            actual_balances=get_balances(res),
            expected_balances={
                start
                + timedelta(hours=2): {
                    "wallet_account": [
                        (SGD_TODAYS_SPENDING, "-100"),
                        (SGD_DEFAULT_DIMENSIONS, "100"),
                        (SGD_PENDING_OUT_DIMENSIONS, "-100"),
                    ],
                    "2": [(SGD_DEFAULT_DIMENSIONS, "-90")],
                },
                start
                + timedelta(hours=3): {
                    "wallet_account": [
                        (SGD_TODAYS_SPENDING, "-110"),
                        (SGD_DEFAULT_DIMENSIONS, "110"),
                        (SGD_PENDING_OUT_DIMENSIONS, "-110"),
                    ],
                    "2": [(SGD_DEFAULT_DIMENSIONS, "-100")],
                },
                start
                + timedelta(hours=4): {
                    "wallet_account": [
                        (SGD_TODAYS_SPENDING, "-110"),
                        (SGD_DEFAULT_DIMENSIONS, "10"),
                        (SGD_PENDING_OUT_DIMENSIONS, "-10"),
                    ],
                    "2": [(SGD_DEFAULT_DIMENSIONS, "-100")],
                },
                start
                + timedelta(hours=5): {
                    "wallet_account": [
                        (SGD_TODAYS_SPENDING, "-120"),
                        (SGD_DEFAULT_DIMENSIONS, "0"),
                        (SGD_PENDING_OUT_DIMENSIONS, "0"),
                    ],
                    "2": [(SGD_DEFAULT_DIMENSIONS, "-110")],
                },
            },
        )

    def test_auto_top_up_does_not_apply_to_other_denoms(self):
        """
        Postings in non-default denominations do not trigger
        auto-top up functionality and are rejected instead
        """

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=3, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_flag_definition_event(timestamp=start, flag_definition_id=AUTO_TOP_UP_FLAG),
            create_flag_event(
                timestamp=start,
                flag_definition_id=AUTO_TOP_UP_FLAG,
                account_id="wallet_account",
                expiry_timestamp=end,
            ),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="10",
                event_datetime=start + timedelta(hours=1),
                denomination="USD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="200",
                event_datetime=start + timedelta(hours=2),
                denomination="USD",
            ),
        ]

        res = self.run_test(start, end, events)

        self.assertEqual(get_num_postings(res, "wallet_account"), 1)
        self.assertEqual(
            get_num_postings(res, "wallet_account", BalanceDimensions("todays_spending")),
            0,
        )

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "wallet_account": {
                    end: [
                        (
                            BalanceDimensions(address="todays_spending", denomination="USD"),
                            "0",
                        ),
                        (USD_DEFAULT_DIMENSIONS, "10"),
                    ]
                },
                "2": {end: [(USD_DEFAULT_DIMENSIONS, "0")]},
            },
        )

    def test_backdated_postings_received_same_day_above_dailylimit_are_rejected(self):
        """
        Ensure backdated outbound postings received on the same day
        once after the daily spending limit is reached are rejected
        """

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=8, tzinfo=timezone.utc)

        instance_parameters = default_instance_params.copy()
        instance_parameters["daily_spending_limit"] = "400"

        events = [
            self.default_create_account_instruction(start, instance_parameters),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="800",
                event_datetime=start,
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="300",
                event_datetime=start + timedelta(hours=3),
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="200",
                event_datetime=start + timedelta(hours=4),
                denomination="SGD",
                value_timestamp=start + timedelta(hours=2),
            ),
        ]

        res = self.run_test(start, end, events, instance_params=instance_parameters)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_DEFAULT_DIMENSIONS, "500")]}},
        )
        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_TODAYS_SPENDING, "-300")]}},
        )

    def test_backdated_postings_received_next_day_are_accepted_with_current_day_limit(
        self,
    ):
        """
        Although when daily spending limit is reached for a previous day,
        ensure backdated outbound postings are received on the next day, smart
        contract refers todays spending value of the processing day and
        postings are accepted
        """

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, hour=8, tzinfo=timezone.utc)

        instance_parameters = default_instance_params.copy()
        instance_parameters["daily_spending_limit"] = "400"

        events = [
            self.default_create_account_instruction(start, instance_parameters),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="800",
                event_datetime=start,
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="400",
                event_datetime=start + timedelta(hours=3),
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="200",
                event_datetime=start + timedelta(days=1, hours=2),
                denomination="SGD",
                value_timestamp=start + timedelta(hours=2),
            ),
        ]

        res = self.run_test(start, end, events, instance_params=instance_parameters)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_DEFAULT_DIMENSIONS, "200")]}},
        )
        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_TODAYS_SPENDING, "-200")]}},
        )

    def test_backdated_postings_received_above_current_day_limit_are_rejected_(
        self,
    ):
        """
        Given daily spending limit is not reached for a previous day
        but reached for current day, When backdated outbound postings received
        on the next day, ensure smart contract refers
        todays spending value of the processing day and postings are rejected
        """

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, hour=8, tzinfo=timezone.utc)

        instance_parameters = default_instance_params.copy()
        instance_parameters["daily_spending_limit"] = "400"

        events = [
            self.default_create_account_instruction(start, instance_parameters),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="800",
                event_datetime=start,
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="100",
                event_datetime=start + timedelta(hours=3),
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="400",
                event_datetime=start + timedelta(days=1, hours=2),
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="200",
                event_datetime=start + timedelta(days=1, hours=3),
                denomination="SGD",
                value_timestamp=start + timedelta(hours=2),
            ),
        ]

        res = self.run_test(start, end, events, instance_params=instance_parameters)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_DEFAULT_DIMENSIONS, "300")]}},
        )
        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_TODAYS_SPENDING, "-400")]}},
        )

    def test_backdated_postings_above_spendlimit_after_parameter_change_are_rejected(
        self,
    ):
        """
        Ensure backdated postings references the parameter value
        at the actual posting time instead of the current value
        """

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, hour=8, tzinfo=timezone.utc)

        instance_parameters = default_instance_params.copy()
        instance_parameters["daily_spending_limit"] = "400"

        events = [
            self.default_create_account_instruction(start, instance_parameters),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="800",
                event_datetime=start,
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="300",
                event_datetime=start + timedelta(hours=2),
                denomination="SGD",
            ),
            create_instance_parameter_change_event(
                timestamp=start + timedelta(hours=3),
                account_id="wallet_account",
                daily_spending_limit="1000",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="300",
                event_datetime=start + timedelta(hours=4),
                denomination="SGD",
                value_timestamp=start + timedelta(hours=2),
            ),
        ]

        res = self.run_test(start, end, events, instance_params=instance_parameters)

        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_DEFAULT_DIMENSIONS, "500")]}},
        )
        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "wallet_account": {start + timedelta(hours=6): [(SGD_TODAYS_SPENDING, "-300")]}
            },
        )

    def test_total_spending_is_accurate_when_two_backdated_debit_postings_are_accepted(
        self,
    ):
        """
        Ensure correct balances are referenced and outstanding balances are correct
        when two backdated postings of different posting times are processed
        anti chronologically
        """

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="500",
                event_datetime=start,
                denomination="SGD",
            ),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="500",
                event_datetime=start + timedelta(minutes=4),
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="600",
                event_datetime=start + timedelta(minutes=5),
                denomination="SGD",
                value_timestamp=start + timedelta(minutes=3),
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="200",
                event_datetime=start + timedelta(minutes=6),
                denomination="SGD",
                value_timestamp=start + timedelta(minutes=2),
            ),
        ]

        res = self.run_test(start, end, events)
        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={"wallet_account": {end: [(SGD_TODAYS_SPENDING, "-800")]}},
        )

    def test_available_balance_accounts_for_settled_and_authorised_funds(self):
        """
        Ensure available balance is reduced by both postings to COMMITTED (aka settled)
        and PENDING_OUTGOING (outbound auth) phases for the default denomination
        """

        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=5, tzinfo=timezone.utc)

        events = [
            self.default_create_account_instruction(start),
            create_inbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="400",
                event_datetime=start + timedelta(hours=1),
                denomination="SGD",
            ),
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="100",
                event_datetime=start + timedelta(hours=2),
                denomination="SGD",
            ),
            create_outbound_authorisation_instruction(
                target_account_id="wallet_account",
                amount="100",
                event_datetime=start + timedelta(hours=3),
                denomination="SGD",
            ),
            # At this point the available balance is 200,
            # so any posting above this should be rejected
            create_outbound_hard_settlement_instruction(
                target_account_id="wallet_account",
                amount="300",
                event_datetime=start + timedelta(hours=4),
                denomination="SGD",
            ),
            create_outbound_authorisation_instruction(
                target_account_id="wallet_account",
                amount="300",
                event_datetime=start + timedelta(hours=5),
                denomination="SGD",
            ),
        ]

        res = self.run_test(start, end, events)

        self.assertEqual(get_num_postings(res, "wallet_account"), 3)
        self.assertEqual(
            get_num_postings(res, "wallet_account", BalanceDimensions("todays_spending")),
            2,
        )
        self.check_balances(
            actual_balances=get_balances(res),
            expected_balances={
                "wallet_account": {
                    end: [
                        (SGD_TODAYS_SPENDING, "-200"),
                        (SGD_DEFAULT_DIMENSIONS, "300"),
                        (SGD_PENDING_OUT_DIMENSIONS, "-100"),
                    ]
                }
            },
        )

    def test_account_closed_after_daily_spending_balance_0(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=5, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="inbound and outbound postings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        internal_account_id=INTERNAL_ACCOUNT,
                        amount="50",
                        event_datetime=start,
                        denomination="SGD",
                    ),
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="50",
                        internal_account_id=INTERNAL_ACCOUNT,
                        event_datetime=start + timedelta(minutes=1),
                        denomination="SGD",
                    ),
                ],
                expected_balances_at_ts={
                    start + timedelta(minutes=2): {WALLET_ACCOUNT: [(SGD_TODAYS_SPENDING, "-50")]}
                },
            ),
            SubTest(
                description="change status",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end,
                        account_id=WALLET_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={end: {WALLET_ACCOUNT: [(SGD_TODAYS_SPENDING, "0")]}},
            ),
        ]

        test_scenario = self._get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_account_closed_daily_spending_balance_nonzero(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=1, hour=5, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="inbound and outbound postings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        internal_account_id=INTERNAL_ACCOUNT,
                        amount="150",
                        event_datetime=start,
                        denomination="SGD",
                    ),
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="50",
                        internal_account_id=INTERNAL_ACCOUNT,
                        event_datetime=start + timedelta(minutes=1),
                        denomination="SGD",
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(minutes=2): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING, "-50"),
                            (SGD_DEFAULT_DIMENSIONS, "100"),
                        ]
                    }
                },
            ),
            SubTest(
                description="change status",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end,
                        account_id=WALLET_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING, "0"),
                            (SGD_DEFAULT_DIMENSIONS, "100"),
                        ]
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
