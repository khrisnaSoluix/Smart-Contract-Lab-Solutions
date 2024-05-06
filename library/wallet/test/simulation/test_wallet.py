# standard libs
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from decimal import Decimal

# library
from library.wallet.contracts.template import wallet
from library.wallet.test import accounts, dimensions, files, parameters
from library.wallet.test.simulation.accounts import default_internal_accounts

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ExpectedRejection,
    ExpectedSchedule,
    SimulationTestScenario,
    SubTest,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    create_account_instruction,
    create_auth_adjustment_instruction,
    create_flag_definition_event,
    create_flag_event,
    create_inbound_hard_settlement_instruction,
    create_instance_parameter_change_event,
    create_outbound_authorisation_instruction,
    create_outbound_hard_settlement_instruction,
    create_release_event,
    create_settlement_event,
    create_transfer_instruction,
    update_account_status_pending_closure,
)
from inception_sdk.test_framework.contracts.simulation.utils import SimulationTestCase

# We don't use the template value as it is a CLU ref that will be substituted
AUTO_TOP_UP_FLAG = "AUTO_TOP_UP_WALLET"

GBP_DEFAULT_DIMENSIONS = dimensions.GBP_DEFAULT_DIMENSIONS
USD_DEFAULT_DIMENSIONS = dimensions.USD_DEFAULT_DIMENSIONS
SGD_DEFAULT_DIMENSIONS = dimensions.DEFAULT_DIMENSIONS
SGD_PENDING_OUT_DIMENSIONS = dimensions.PENDING_OUT_DIMENSIONS
SGD_TODAYS_SPENDING_DIMENSIONS = dimensions.TODAYS_SPENDING_DIMENSIONS

WALLET_ACCOUNT = accounts.WALLET_ACCOUNT
NOMINATED_ACCOUNT = accounts.NOMINATED_ACCOUNT

default_instance_params = {**parameters.default_instance}
default_template_params = {**parameters.default_template}


class WalletTest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_filepaths = [files.WALLET_CONTRACT]
        cls.contract_modules = []
        super().setUpClass()

    def get_simulation_test_scenario(
        self,
        start,
        end,
        sub_tests,
        template_params=None,
        instance_params=None,
        internal_accounts=None,
        debug=False,
    ):
        contract_config = ContractConfig(
            contract_content=self.smart_contract_path_to_content[files.WALLET_CONTRACT],
            template_params=template_params or default_template_params,
            account_configs=[
                AccountConfig(
                    instance_params=instance_params or default_instance_params,
                    account_id_base=WALLET_ACCOUNT,
                )
            ],
        )
        return SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=internal_accounts or default_internal_accounts,
            debug=debug,
        )

    def test_account_opening(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="check balances after account opening",
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_change_customer_limit_no_balance_no_sweep_have_balance_sweep(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Change customer wallet limit but no balance yet,"
                " so no sweep should happen",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start_datetime,
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_CUSTOMER_WALLET_LIMIT: "500"},
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "0")],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "0")],
                    },
                },
            ),
            SubTest(
                description="Has balance so sweep should happen",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="600",
                        event_datetime=start_datetime + timedelta(minutes=3),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=2): {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "0")],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "0")],
                    },
                    start_datetime
                    + timedelta(minutes=3): {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "500")],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "100")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_change_customer_limit_balance_no_sweep(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Deposit to wallet",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="450",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("450")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
            SubTest(
                description="Change wallet limit no sweep should happen since "
                "wallet is below limit",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start_datetime + timedelta(minutes=1),
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_CUSTOMER_WALLET_LIMIT: "500"},
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("450")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_change_customer_limit_balance_sweep(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        sub_tests = [
            SubTest(
                description="Deposit money to wallet",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="1000",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("1000")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
            SubTest(
                description="Sweep should happen since balance is in excess of limit",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start_datetime + timedelta(minutes=1),
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_CUSTOMER_WALLET_LIMIT: "500"},
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("500")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("500"))],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_multiple_balance_sweeps_same_day(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Deposit money",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="1000",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("1000")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
            SubTest(
                description="1st sweep",
                events=[
                    create_instance_parameter_change_event(
                        # 1000-800 = 200 sweep
                        timestamp=start_datetime + timedelta(minutes=1),
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_CUSTOMER_WALLET_LIMIT: "800"},
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=1): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("800")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("200"))],
                    }
                },
            ),
            SubTest(
                description="2nd Sweep.",
                events=[
                    create_instance_parameter_change_event(
                        # 800 - 500 = 300 sweep
                        timestamp=start_datetime + timedelta(minutes=2),
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_CUSTOMER_WALLET_LIMIT: "500"},
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=2): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("500")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("500"))],
                    }
                },
            ),
            SubTest(
                description="No sweep",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start_datetime + timedelta(minutes=3),
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_CUSTOMER_WALLET_LIMIT: "600"},
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("500")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("500"))],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_multiple_balance_sweeps_different_day(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=5, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Deposit wallet",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="1000",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            # 200 and 300 sweep.
                            (SGD_DEFAULT_DIMENSIONS, Decimal("1000")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
            SubTest(
                description="1st balance sweep.",
                events=[
                    create_instance_parameter_change_event(
                        # 1000-800=200
                        timestamp=start_datetime + timedelta(days=1),
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_CUSTOMER_WALLET_LIMIT: "800"},
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(days=1): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("800")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("200"))],
                    }
                },
            ),
            SubTest(
                description="2nd balance sweep",
                events=[
                    create_instance_parameter_change_event(
                        # 800-500=300
                        timestamp=start_datetime + timedelta(days=2),
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_CUSTOMER_WALLET_LIMIT: "500"},
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("500")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("500"))],
                    }
                },
            ),
            SubTest(
                description="No sweep",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start_datetime + timedelta(days=3),
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_CUSTOMER_WALLET_LIMIT: "600"},
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            # 200 and 300 sweep.
                            (SGD_DEFAULT_DIMENSIONS, Decimal("500")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("500"))],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_multiple_param_changes_same_day_no_sweep(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        sub_tests = [
            SubTest(
                description="Deposit to wallet",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="1000",
                        event_datetime=start,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("1000")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
            SubTest(
                description="1st param change",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + timedelta(minutes=1),
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_CUSTOMER_WALLET_LIMIT: "1200"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(minutes=1): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("1000")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
            SubTest(
                description="2nd parameter change",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + timedelta(minutes=2),
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_CUSTOMER_WALLET_LIMIT: "1500"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(minutes=2): {
                        WALLET_ACCOUNT: [
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
            SubTest(
                description="3rd parameter change",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + timedelta(minutes=3),
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_CUSTOMER_WALLET_LIMIT: "2000"},
                    ),
                ],
                expected_balances_at_ts={
                    start
                    + timedelta(minutes=3): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("1000")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
            SubTest(
                description="Last parameter change",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start + timedelta(minutes=4),
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_NOMINATED_ACCOUNT: "Some Other Account"},
                    ),
                ],
                expected_balances_at_ts={
                    end: {
                        WALLET_ACCOUNT: [
                            # 200 and 300 sweep.
                            (SGD_DEFAULT_DIMENSIONS, Decimal("1000")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_spending_is_mirrored(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Deposit Money to wallet",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="50",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("50")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
            SubTest(
                description="Spend money",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="50",
                        event_datetime=start_datetime + timedelta(minutes=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("-50")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_spending_is_mirrored_for_secondary_instructions(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=5, tzinfo=timezone.utc)
        sub_tests = [
            SubTest(
                description="Deposit to wallet",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="1000",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, Decimal("1000")),
                            (USD_DEFAULT_DIMENSIONS, Decimal("0")),
                            (SGD_PENDING_OUT_DIMENSIONS, Decimal("0")),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, Decimal("0")),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
            SubTest(
                description="Spend money with authorisation",
                events=[
                    create_outbound_authorisation_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="500",
                        event_datetime=start_datetime + timedelta(hours=1),
                        denomination=parameters.TEST_DENOMINATION,
                        client_transaction_id="A",
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=1): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-500"),
                            (SGD_DEFAULT_DIMENSIONS, "1000"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-500"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    },
                },
            ),
            SubTest(
                description="Reduce authorisation spending.",
                events=[
                    # The auth adjust is reduced, which should decrease today's spending
                    create_auth_adjustment_instruction(
                        amount="-100",
                        client_transaction_id="A",
                        event_datetime=start_datetime + timedelta(hours=2),
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=2): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-400"),
                            (SGD_DEFAULT_DIMENSIONS, "1000"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-400"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    },
                },
            ),
            SubTest(
                description="Increase authorise spending",
                events=[
                    # The increase should increase today's spending
                    create_auth_adjustment_instruction(
                        amount="100",
                        client_transaction_id="A",
                        event_datetime=start_datetime + timedelta(hours=3),
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=3): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-500"),
                            (SGD_DEFAULT_DIMENSIONS, "1000"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-500"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    }
                },
            ),
            SubTest(
                description="Partial settlement",
                events=[
                    # permanently increase today's spending (until reset at EOD)
                    create_settlement_event(
                        client_transaction_id="A",
                        amount="100",
                        final=False,
                        event_datetime=start_datetime + timedelta(hours=4),
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=4): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-500"),
                            (SGD_DEFAULT_DIMENSIONS, "900"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-400"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    },
                },
            ),
            SubTest(
                description="Release remaining authorisation",
                events=[
                    # The release should clear today's spending
                    create_release_event(
                        client_transaction_id="A",
                        event_datetime=start_datetime + timedelta(hours=5),
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=5): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-100"),
                            (SGD_DEFAULT_DIMENSIONS, "900"),
                            (SGD_PENDING_OUT_DIMENSIONS, "0"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, Decimal("0"))],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_spending_is_mirrored_multiple_postings(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)
        sub_tests = [
            SubTest(
                description="Deposit to wallet",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="100",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "100"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Send 1st payment",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="40",
                        event_datetime=start_datetime + timedelta(minutes=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=1): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "60"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-40"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Test second payment",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="60",
                        event_datetime=start_datetime + timedelta(minutes=2),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "0"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-100"),
                        ],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_spending_is_zeroed_out_at_midnight(self):
        """
        Test that the correct schedules to zero out daily spend are
        created when the account is instantiated and the todays spending
        is zeroed out.
        """
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        posting_datetime = start_datetime + timedelta(minutes=1)

        zero_out_daily_spend_event_datetime = start_datetime + relativedelta(
            hour=int(default_template_params["zero_out_daily_spend_hour"]),
            minute=int(default_template_params["zero_out_daily_spend_minute"]),
            second=int(default_template_params["zero_out_daily_spend_second"]),
        )

        sub_tests = [
            SubTest(
                description="Deposit money",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="50",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "50"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Make payment",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="50",
                        event_datetime=posting_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    posting_datetime: {
                        WALLET_ACCOUNT: [(SGD_TODAYS_SPENDING_DIMENSIONS, "-50")],
                    },
                },
            ),
            SubTest(
                description="Reset spending to zero",
                events=[],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [(SGD_TODAYS_SPENDING_DIMENSIONS, "0")],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            zero_out_daily_spend_event_datetime,
                        ],
                        event_id="ZERO_OUT_DAILY_SPEND",
                        account_id=WALLET_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_spending_is_zeroed_out_at_updated_params_value(self):
        """
        Test that the correct schedules to zero out daily spend are
        created when the account is instantiated with a change in
        default schedule parameter values and the todays spending
        is zeroed out.
        """
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=2, hour=2, tzinfo=timezone.utc)

        posting_datetime = start_datetime + timedelta(minutes=1)
        template_params = {
            **default_template_params,
            wallet.PARAM_ZERO_OUT_DAILY_SPEND_HOUR: "1",
            wallet.PARAM_ZERO_OUT_DAILY_SPEND_MINUTE: "0",
            wallet.PARAM_ZERO_OUT_DAILY_SPEND_SECOND: "0",
        }

        zero_out_daily_spend_event_datetime = start_datetime + relativedelta(
            hour=int(template_params[wallet.PARAM_ZERO_OUT_DAILY_SPEND_HOUR]),
            minute=int(template_params[wallet.PARAM_ZERO_OUT_DAILY_SPEND_MINUTE]),
            second=int(template_params[wallet.PARAM_ZERO_OUT_DAILY_SPEND_SECOND]),
        )
        sub_tests = [
            SubTest(
                description="Deposit money",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="50",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "50"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                        ],
                    },
                },
            ),
            SubTest(
                description="Make payment",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="50",
                        event_datetime=posting_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    posting_datetime: {
                        WALLET_ACCOUNT: [(SGD_TODAYS_SPENDING_DIMENSIONS, "-50")],
                    },
                },
            ),
            SubTest(
                description="Zero out schedule run",
                events=[],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [(SGD_TODAYS_SPENDING_DIMENSIONS, "-0")],
                    },
                },
                expected_schedules=[
                    ExpectedSchedule(
                        run_times=[
                            zero_out_daily_spend_event_datetime,
                        ],
                        event_id="ZERO_OUT_DAILY_SPEND",
                        account_id=WALLET_ACCOUNT,
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            template_params=template_params,
        )
        self.run_test_scenario(test_scenario)

    def test_postings_above_limit_are_rejected(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        instance_params = {**default_instance_params, wallet.PARAM_SPENDING_LIMIT: "400"}
        sub_tests = [
            SubTest(
                description="Deposit money",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="500",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "500")],
                    },
                },
            ),
            SubTest(
                description="Above the limit posting",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="450",
                        event_datetime=start_datetime + timedelta(minutes=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=1): {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "500")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(minutes=1),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction would exceed daily spending limit",
                    ),
                ],
            ),
            SubTest(
                description="Slightly above the limit posting",
                events=[
                    # Slightly above limit
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="400.01",
                        event_datetime=start_datetime + timedelta(minutes=2),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=2): {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "500")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(minutes=2),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction would exceed daily spending limit",
                    ),
                ],
            ),
            SubTest(
                description="On the limit.",
                events=[
                    # On the limit
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="400",
                        event_datetime=start_datetime + timedelta(minutes=4),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "100")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_postings_above_limit_are_rejected_multiple_postings(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        instance_params = {**default_instance_params, wallet.PARAM_SPENDING_LIMIT: "400"}
        sub_tests = [
            SubTest(
                description="Make a deposit.",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="500",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "500"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st posting within limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="200",
                        event_datetime=start_datetime + timedelta(minutes=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=1): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "300"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-200"),
                        ],
                    }
                },
            ),
            SubTest(
                description="2nd posting within limit",
                events=[
                    create_outbound_authorisation_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="200",
                        event_datetime=start_datetime + timedelta(minutes=2),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=2): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "300"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-200"),
                        ],
                    }
                },
            ),
            SubTest(
                description="1st rejected posting",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="50",
                        event_datetime=start_datetime + timedelta(minutes=3),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=3): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "300"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-200"),
                        ],
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(minutes=3),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction would exceed daily spending limit",
                    ),
                ],
            ),
            SubTest(
                description="2nd rejected posting",
                events=[
                    create_outbound_authorisation_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="50",
                        event_datetime=start_datetime + timedelta(minutes=4),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "300"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-200"),
                        ],
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(minutes=4),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction would exceed daily spending limit",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_balance_cannot_go_above_limit_swept_out(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Test balance cannot go above limit swept out.",
                events=[
                    create_transfer_instruction(
                        creditor_target_account_id=WALLET_ACCOUNT,
                        debtor_target_account_id="1",
                        amount="9999",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "1000")],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "8999")],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_topped_up_balances_due_to_auth_is_swept_after_auth_adjust_and_release(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=4, tzinfo=timezone.utc)

        TRANSACTION_ID = "A"

        sub_tests = [
            SubTest(
                description="Setup auto top-up and authorise payment from empty wallet",
                events=[
                    create_flag_definition_event(
                        timestamp=start_datetime, flag_definition_id=AUTO_TOP_UP_FLAG
                    ),
                    create_flag_event(
                        timestamp=start_datetime,
                        flag_definition_id=AUTO_TOP_UP_FLAG,
                        account_id=WALLET_ACCOUNT,
                        expiry_timestamp=end_datetime,
                    ),
                    create_outbound_authorisation_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="1500",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                        client_transaction_id=TRANSACTION_ID,
                    ),
                ],
                expected_balances_at_ts={
                    # Available balance = 1500 - 1500 = 0, so no sweep
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-1500"),
                            (SGD_DEFAULT_DIMENSIONS, "1500"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-1500"),
                        ],
                        NOMINATED_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "-1500"),  # Used to top up the wallet
                        ],
                    }
                },
            ),
            SubTest(
                description="Reduce the authorisation amount to push the wallet above its limit",
                events=[
                    # Available balance = 0 + 1100 = 1100, so sweep
                    create_auth_adjustment_instruction(
                        amount="-1100",
                        client_transaction_id=TRANSACTION_ID,
                        event_datetime=start_datetime + timedelta(hours=1),
                    ),
                ],
                expected_balances_at_ts={
                    # The available balance (1100 SGD) is above the wallet's limit (1000 SGD),
                    # so 100 SGD are swept back into the nominated account and the available
                    # balance becomes: 1400 (default) - 400 (pending) = 1000
                    start_datetime
                    + timedelta(hours=1): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-400"),
                            (SGD_DEFAULT_DIMENSIONS, "1400"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-400"),
                        ],
                        NOMINATED_ACCOUNT: [
                            # 100 SGD are swept back into the account
                            (SGD_DEFAULT_DIMENSIONS, "-1400"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Increase the authorisation amount",
                events=[
                    # Available balance = 1000 - 1000 = 0, so no sweep
                    create_auth_adjustment_instruction(
                        amount="1000",
                        client_transaction_id=TRANSACTION_ID,
                        event_datetime=start_datetime + timedelta(hours=2),
                    ),
                ],
                expected_balances_at_ts={
                    # There is enough available balance to cover the adjustment
                    # so no funds get moved
                    start_datetime
                    + timedelta(hours=2): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-1400"),
                            (SGD_DEFAULT_DIMENSIONS, "1400"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-1400"),
                        ],
                        NOMINATED_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "-1400"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Release the funds",
                events=[
                    # Available balance = 0 + 1000 = 1000, so no sweep
                    create_release_event(
                        client_transaction_id=TRANSACTION_ID,
                        event_datetime=start_datetime + timedelta(hours=3),
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=3): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                            (SGD_DEFAULT_DIMENSIONS, "1000"),
                            (SGD_PENDING_OUT_DIMENSIONS, "0"),
                        ],
                        NOMINATED_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "-1000"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_postings_above_limit_are_not_rejected_with_refund(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        instance_params = {**default_instance_params, wallet.PARAM_SPENDING_LIMIT: "400"}

        sub_tests = [
            SubTest(
                description="Deposit to wallet",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="500",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "500"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                            (SGD_PENDING_OUT_DIMENSIONS, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="make 1st payment",
                events=[
                    create_outbound_authorisation_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="400",
                        event_datetime=start_datetime + timedelta(minutes=1),
                        denomination=parameters.TEST_DENOMINATION,
                        client_transaction_id="A",
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=1): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "500"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-400"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-400"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Make refund.",
                events=[
                    # Refund here
                    create_auth_adjustment_instruction(
                        amount="-400",
                        client_transaction_id="A",
                        event_datetime=start_datetime + timedelta(minutes=2),
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=2): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "500"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                            (SGD_PENDING_OUT_DIMENSIONS, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Use refunded money",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="399",
                        event_datetime=start_datetime + timedelta(minutes=3),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "101"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-399"),
                            (SGD_PENDING_OUT_DIMENSIONS, "0"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_postings_above_limit_are_rejected_with_non_refund(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        instance_params = {**default_instance_params, wallet.PARAM_SPENDING_LIMIT: "400"}

        sub_tests = [
            SubTest(
                description="Make deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="500",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "500"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Make first repayment",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="400",
                        event_datetime=start_datetime + timedelta(minutes=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=1): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "100"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-400"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Make second deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="400",
                        event_datetime=start_datetime + timedelta(minutes=2),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=2): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "500"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-400"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Reject posting for exceeding daily limit",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="400",
                        event_datetime=start_datetime + timedelta(minutes=3),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "500"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-400"),
                        ],
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(minutes=3),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction would exceed daily spending limit",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_additional_denom_can_be_spent_not_exceeded(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=3, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Deposit money",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="1000",
                        event_datetime=start_datetime + timedelta(hours=1),
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=1): {
                        WALLET_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "1000")],
                    }
                },
            ),
            SubTest(
                description="1st payment",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="200",
                        event_datetime=start_datetime + timedelta(hours=2),
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=2): {
                        WALLET_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "800")],
                    }
                },
            ),
            SubTest(
                description="Posting rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="900",
                        event_datetime=start_datetime + timedelta(hours=3),
                        denomination="GBP",
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [(GBP_DEFAULT_DIMENSIONS, "800")],
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(hours=3),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total GBP -900, which exceeds the available"
                        " balance of GBP 800",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_posting_rejected_if_exceeding_balance_and_auto_top_up_disabled(self):
        """Ensure the balance stays zero with false flag"""

        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=3, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Rejected if exceeding balance and auto-top up disabled.",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="200",
                        event_datetime=start_datetime + timedelta(hours=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "0")],
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(hours=1),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total SGD -200, which exceeds the available"
                        " balance of SGD 0 and auto top up is disabled",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_posting_rejected_if_unsupported_denom(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=3, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Test posting rejected if unsupported denomination",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="10",
                        event_datetime=start_datetime + timedelta(hours=1),
                        denomination="HKD",
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "0"),
                            (BalanceDimensions(denomination="HKD"), "0"),
                        ],
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(hours=1),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="WrongDenomination",
                        rejection_reason="Postings received in unauthorised denominations",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_auto_top_up_triggered_when_flag_is_set(self):

        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=3, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Configure flag and set initial deposit",
                events=[
                    create_flag_definition_event(
                        timestamp=start_datetime, flag_definition_id=AUTO_TOP_UP_FLAG
                    ),
                    create_flag_event(
                        timestamp=start_datetime,
                        flag_definition_id=AUTO_TOP_UP_FLAG,
                        account_id=WALLET_ACCOUNT,
                        expiry_timestamp=end_datetime,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="10",
                        event_datetime=start_datetime + timedelta(hours=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=1): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                            (SGD_DEFAULT_DIMENSIONS, "10"),
                        ],
                    }
                },
            ),
            SubTest(
                description="Auto top up should happen",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="200",
                        event_datetime=start_datetime + timedelta(hours=2),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-200"),
                            (SGD_DEFAULT_DIMENSIONS, "0"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "-190")],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_auto_top_up_triggered_when_flag_is_set_for_auth_and_settle(self):

        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=6, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Setup flags and initial deposit",
                events=[
                    create_flag_definition_event(
                        timestamp=start_datetime, flag_definition_id=AUTO_TOP_UP_FLAG
                    ),
                    create_flag_event(
                        timestamp=start_datetime,
                        flag_definition_id=AUTO_TOP_UP_FLAG,
                        account_id=WALLET_ACCOUNT,
                        expiry_timestamp=end_datetime,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="10",
                        event_datetime=start_datetime + timedelta(hours=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=1): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                            (SGD_DEFAULT_DIMENSIONS, "10"),
                            (SGD_PENDING_OUT_DIMENSIONS, "0"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "0")],
                    },
                },
            ),
            SubTest(
                description="Do Authorisation",
                events=[
                    # We expect authorisations to behave equally to hard settlements
                    # as they affect available balance
                    create_outbound_authorisation_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="100",
                        event_datetime=start_datetime + timedelta(hours=2),
                        denomination=parameters.TEST_DENOMINATION,
                        client_transaction_id="A",
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=2): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-100"),
                            (SGD_DEFAULT_DIMENSIONS, "100"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-100"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "-90")],
                    },
                },
            ),
            SubTest(
                description="Auth adjust and add more payments",
                events=[
                    # Auth adjust behaves as an additional auth
                    create_auth_adjustment_instruction(
                        amount="10",
                        client_transaction_id="A",
                        event_datetime=start_datetime + timedelta(hours=3),
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=3): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-110"),
                            (SGD_DEFAULT_DIMENSIONS, "110"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-110"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "-100")],
                    },
                },
            ),
            SubTest(
                description="Create settlement",
                events=[
                    # Settlements have no impact as there is no change to available balance
                    create_settlement_event(
                        amount="100",
                        event_datetime=start_datetime + timedelta(hours=4),
                        client_transaction_id="A",
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=4): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-110"),
                            (SGD_DEFAULT_DIMENSIONS, "10"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-10"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "-100")],
                    },
                },
            ),
            SubTest(
                description="Over settlement",
                events=[
                    # Over settling triggers more top-up
                    create_settlement_event(
                        amount="20",
                        event_datetime=start_datetime + timedelta(hours=5),
                        client_transaction_id="A",
                        final=True,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=5): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-120"),
                            (SGD_DEFAULT_DIMENSIONS, "0"),
                            (SGD_PENDING_OUT_DIMENSIONS, "0"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "-110")],
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_auto_top_up_does_not_apply_to_other_denoms(self):
        """
        Postings in non-default denominations do not trigger
        auto-top up functionality and are rejected instead
        """

        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=3, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Setup flag and initial deposit",
                events=[
                    create_flag_definition_event(
                        timestamp=start_datetime, flag_definition_id=AUTO_TOP_UP_FLAG
                    ),
                    create_flag_event(
                        timestamp=start_datetime,
                        flag_definition_id=AUTO_TOP_UP_FLAG,
                        account_id=WALLET_ACCOUNT,
                        expiry_timestamp=end_datetime,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="10",
                        event_datetime=start_datetime + timedelta(hours=1),
                        denomination="USD",
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=1): {
                        WALLET_ACCOUNT: [
                            (
                                BalanceDimensions(
                                    address=wallet.TODAYS_SPENDING, denomination="USD"
                                ),
                                "0",
                            ),
                            (USD_DEFAULT_DIMENSIONS, "10"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "0")],
                    },
                },
            ),
            SubTest(
                description="Make payment",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="200",
                        event_datetime=start_datetime + timedelta(hours=2),
                        denomination="USD",
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (
                                BalanceDimensions(
                                    address=wallet.TODAYS_SPENDING, denomination="USD"
                                ),
                                "0",
                            ),
                            (USD_DEFAULT_DIMENSIONS, "10"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "0")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(hours=2),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total USD -200, which exceeds"
                        " the available balance of USD 10",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_auto_top_up_not_triggered_when_daily_limit_reached(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        instance_params = {**default_instance_params, wallet.PARAM_SPENDING_LIMIT: "500"}

        sub_tests = [
            SubTest(
                description="Inbound and outbound postings to reach daily spending limit",
                events=[
                    create_flag_definition_event(
                        timestamp=start_datetime, flag_definition_id=AUTO_TOP_UP_FLAG
                    ),
                    create_flag_event(
                        timestamp=start_datetime,
                        flag_definition_id=AUTO_TOP_UP_FLAG,
                        account_id=WALLET_ACCOUNT,
                        expiry_timestamp=end_datetime,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="400",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="500",
                        event_datetime=start_datetime + timedelta(minutes=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    # Auto top-up should work
                    start_datetime
                    + timedelta(minutes=2): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "0"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-500"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "-100")],
                    },
                },
            ),
            SubTest(
                description="Auto top-up should not work when daily limit is reached",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="400",
                        event_datetime=start_datetime + timedelta(minutes=3),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=4): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "0"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-500"),
                        ],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "-100")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        timestamp=start_datetime + timedelta(minutes=3),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction would exceed daily spending limit",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_backdated_postings_received_same_day_above_dailylimit_are_rejected(self):
        """
        Ensure backdated outbound postings received on the same day
        once after the daily spending limit is reached are rejected
        """

        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=8, tzinfo=timezone.utc)

        instance_params = {**default_instance_params, wallet.PARAM_SPENDING_LIMIT: "400"}

        sub_tests = [
            SubTest(
                description="Initial deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="800",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "800"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Make payment",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="300",
                        event_datetime=start_datetime + timedelta(hours=3),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=3): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "500"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-300"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Backdated posting should get rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="200",
                        event_datetime=start_datetime + timedelta(hours=4),
                        denomination=parameters.TEST_DENOMINATION,
                        value_timestamp=start_datetime + timedelta(hours=2),
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "500"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-300"),
                        ]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(hours=4),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction would exceed daily spending limit",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_backdated_postings_received_next_day_are_accepted_with_current_day_limit(
        self,
    ):
        """
        Although when daily spending limit is reached for a previous day,
        ensure backdated outbound postings are received on the next day, smart
        contract refers todays spending value of the processing day and
        postings are accepted
        """

        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=2, hour=8, tzinfo=timezone.utc)

        instance_params = {**default_instance_params, wallet.PARAM_SPENDING_LIMIT: "400"}

        sub_tests = [
            SubTest(
                description="Initial deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="800",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "800"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Make 1st payment",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="400",
                        event_datetime=start_datetime + timedelta(hours=3),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                # Due to backdated postings the expected balance is different
                # and postings that spend money from the wallet already happened.
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=3): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "200"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-400"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Backdated posting should get accepted",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="200",
                        event_datetime=start_datetime + timedelta(days=1, hours=2),
                        denomination=parameters.TEST_DENOMINATION,
                        value_timestamp=start_datetime + timedelta(hours=2),
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "200"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-200"),
                        ]
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_backdated_postings_received_above_current_day_limit_are_rejected_(
        self,
    ):
        """
        Given daily spending limit is not reached for a previous day
        but reached for current day, When backdated outbound postings received
        on the next day, ensure smart contract refers
        todays spending value of the processing day and postings are rejected
        """

        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=2, hour=8, tzinfo=timezone.utc)

        instance_params = {**default_instance_params, wallet.PARAM_SPENDING_LIMIT: "400"}

        sub_tests = [
            SubTest(
                description="Initial Deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="800",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "800"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Make first payment",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="100",
                        event_datetime=start_datetime + timedelta(hours=3),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "300"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-400"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Make 2nd payment",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="400",
                        event_datetime=start_datetime + timedelta(days=1, hours=2),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(days=1, hours=2): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "300"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-400"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Test backdated postings received above current day limit are rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="200",
                        event_datetime=start_datetime + timedelta(days=1, hours=3),
                        denomination=parameters.TEST_DENOMINATION,
                        value_timestamp=start_datetime + timedelta(hours=2),
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "300"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-400"),
                        ]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(days=1, hours=3),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction would exceed daily spending limit",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_backdated_postings_above_spendlimit_after_parameter_change_are_rejected(
        self,
    ):
        """
        Ensure backdated postings references the parameter value
        at the actual posting time instead of the current value
        """

        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=2, hour=8, tzinfo=timezone.utc)

        instance_params = {**default_instance_params, wallet.PARAM_SPENDING_LIMIT: "400"}

        sub_tests = [
            SubTest(
                description="Initial deposit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="800",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime: {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "800")],
                    },
                },
            ),
            SubTest(
                description="make 1st payment",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="300",
                        event_datetime=start_datetime + timedelta(hours=2),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=2): {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "500")],
                    },
                },
            ),
            SubTest(
                description="Change param and make a posting to exceed daily limit",
                events=[
                    create_instance_parameter_change_event(
                        timestamp=start_datetime + timedelta(hours=3),
                        account_id=WALLET_ACCOUNT,
                        **{wallet.PARAM_SPENDING_LIMIT: "1000"},
                    ),
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="300",
                        event_datetime=start_datetime + timedelta(hours=4),
                        denomination=parameters.TEST_DENOMINATION,
                        value_timestamp=start_datetime + timedelta(hours=2),
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "500")],
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(hours=4),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="AgainstTermsAndConditions",
                        rejection_reason="Transaction would exceed daily spending limit",
                    )
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_total_spending_is_accurate_when_two_backdated_debit_postings_are_accepted(
        self,
    ):
        """
        Ensure correct balances are referenced and outstanding balances are correct
        when two backdated postings of different posting times are processed
        anti chronologically
        """

        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Make initial deposits",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="500",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="500",
                        event_datetime=start_datetime + timedelta(minutes=4),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                # Due to backdated postings the expected balance is different
                # and postings that spend money from the wallet already happened.
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=4): {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "200"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-800"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Create 2 backdate postings",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="600",
                        event_datetime=start_datetime + timedelta(minutes=5),
                        denomination=parameters.TEST_DENOMINATION,
                        value_timestamp=start_datetime + timedelta(minutes=3),
                    ),
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="200",
                        event_datetime=start_datetime + timedelta(minutes=6),
                        denomination=parameters.TEST_DENOMINATION,
                        value_timestamp=start_datetime + timedelta(minutes=2),
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "200"),
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-800"),
                        ]
                    },
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_available_balance_accounts_for_settled_and_authorised_funds(self):
        """
        Ensure available balance is reduced by both postings to COMMITTED (aka settled)
        and PENDING_OUTGOING (outbound auth) phases for the default denomination
        """

        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=5, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="Initial setup deposit to wallet",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="400",
                        event_datetime=start_datetime + timedelta(hours=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=1): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                            (SGD_DEFAULT_DIMENSIONS, "400"),
                            (SGD_PENDING_OUT_DIMENSIONS, "0"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Do 2 payments so next postings get rejected",
                events=[
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="100",
                        event_datetime=start_datetime + timedelta(hours=2),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    create_outbound_authorisation_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="100",
                        event_datetime=start_datetime + timedelta(hours=3),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-200"),
                            (SGD_DEFAULT_DIMENSIONS, "300"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-100"),
                        ]
                    },
                },
            ),
            SubTest(
                description="Rejected posting",
                events=[
                    # At this point the available balance is 200,
                    # so any posting above this should be rejected
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="300",
                        event_datetime=start_datetime + timedelta(hours=4),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=4): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-200"),
                            (SGD_DEFAULT_DIMENSIONS, "300"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-100"),
                        ]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(hours=4),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total SGD -300, which exceeds the available "
                        "balance of SGD 200 and auto top up is disabled",
                    ),
                ],
            ),
            SubTest(
                description="Rejected 2nd posting",
                events=[
                    # At this point the available balance is 200,
                    # so any posting above this should be rejected
                    create_outbound_authorisation_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="300",
                        event_datetime=start_datetime + timedelta(hours=5),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(hours=5): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-200"),
                            (SGD_DEFAULT_DIMENSIONS, "300"),
                            (SGD_PENDING_OUT_DIMENSIONS, "-100"),
                        ]
                    },
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start_datetime + timedelta(hours=5),
                        account_id=WALLET_ACCOUNT,
                        rejection_type="InsufficientFunds",
                        rejection_reason="Postings total SGD -300, which exceeds the available "
                        "balance of SGD 200 and auto top up is disabled",
                    ),
                ],
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_daily_spending_balance_0_after_account_pending_closure(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=5, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="inbound and outbound postings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="50",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="50",
                        event_datetime=start_datetime + timedelta(minutes=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=2): {
                        WALLET_ACCOUNT: [(SGD_TODAYS_SPENDING_DIMENSIONS, "-50")]
                    }
                },
            ),
            SubTest(
                description="change status",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end_datetime,
                        account_id=WALLET_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {WALLET_ACCOUNT: [(SGD_TODAYS_SPENDING_DIMENSIONS, "0")]}
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_account_closed_daily_spending_balance_nonzero(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=5, tzinfo=timezone.utc)

        sub_tests = [
            SubTest(
                description="inbound and outbound postings",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="150",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="50",
                        event_datetime=start_datetime + timedelta(minutes=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=2): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-50"),
                            (SGD_DEFAULT_DIMENSIONS, "100"),
                        ]
                    }
                },
            ),
            SubTest(
                description="change status",
                events=[
                    update_account_status_pending_closure(
                        timestamp=end_datetime,
                        account_id=WALLET_ACCOUNT,
                    ),
                ],
                expected_balances_at_ts={
                    end_datetime: {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "0"),
                            (SGD_DEFAULT_DIMENSIONS, "100"),
                        ]
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)

    def test_allow_transfer_to_nominated_account_after_daily_spending_limit(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=5, tzinfo=timezone.utc)

        instance_params = {**default_instance_params, wallet.PARAM_SPENDING_LIMIT: "500"}

        sub_tests = [
            SubTest(
                description="Inbound and outbound postings to reach daily spending limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="700",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    create_outbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="500",
                        event_datetime=start_datetime + timedelta(minutes=1),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=2): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-500"),
                            (SGD_DEFAULT_DIMENSIONS, "200"),
                        ],
                    }
                },
            ),
            SubTest(
                description="The transfer should be accepted without increasing the today's "
                "spending address",
                events=[
                    create_transfer_instruction(
                        amount="100",
                        denomination=parameters.TEST_DENOMINATION,
                        event_datetime=start_datetime + timedelta(minutes=3),
                        creditor_target_account_id=NOMINATED_ACCOUNT,
                        debtor_target_account_id=WALLET_ACCOUNT,
                        instruction_details={"withdrawal_to_nominated_account": "True"},
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=4): {
                        WALLET_ACCOUNT: [
                            (SGD_TODAYS_SPENDING_DIMENSIONS, "-500"),
                            (SGD_DEFAULT_DIMENSIONS, "100"),
                        ],
                        NOMINATED_ACCOUNT: [
                            (SGD_DEFAULT_DIMENSIONS, "100"),
                        ],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_move_excess_funds_to_nominated_account(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        instance_params = {**default_instance_params, wallet.PARAM_CUSTOMER_WALLET_LIMIT: "500"}

        sub_tests = [
            SubTest(
                description="Inbound posting to reach wallet limit",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="500",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=1): {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "500")],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "0")],
                    }
                },
            ),
            SubTest(
                description="Inbound posting after the wallet limit has been reached",
                events=[
                    create_inbound_hard_settlement_instruction(
                        target_account_id=WALLET_ACCOUNT,
                        amount="300",
                        event_datetime=start_datetime + timedelta(minutes=2),
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=3): {
                        WALLET_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "500")],
                        NOMINATED_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "300")],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
            instance_params=instance_params,
        )
        self.run_test_scenario(test_scenario)

    def test_transfer_between_accounts(self):
        start_datetime = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end_datetime = datetime(year=2019, month=1, day=1, hour=1, tzinfo=timezone.utc)

        CUSTOMER_X_ACCOUNT = "wallet_account_1"
        CUSTOMER_Y_ACCOUNT = "wallet_account_2"

        sub_tests = [
            SubTest(
                description="Setup accounts",
                events=[
                    create_account_instruction(
                        timestamp=start_datetime,
                        account_id=CUSTOMER_X_ACCOUNT,
                        product_id="0",
                        instance_param_vals=default_instance_params,
                    ),
                    create_account_instruction(
                        timestamp=start_datetime,
                        account_id=CUSTOMER_Y_ACCOUNT,
                        product_id="0",
                        instance_param_vals=default_instance_params,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=CUSTOMER_X_ACCOUNT,
                        amount="100",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                    create_inbound_hard_settlement_instruction(
                        target_account_id=CUSTOMER_Y_ACCOUNT,
                        amount="100",
                        event_datetime=start_datetime,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=1): {
                        CUSTOMER_X_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "100")],
                        CUSTOMER_Y_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "100")],
                    }
                },
            ),
            SubTest(
                description="Transfer funds between accounts",
                events=[
                    create_transfer_instruction(
                        amount="50",
                        event_datetime=start_datetime + timedelta(minutes=2),
                        creditor_target_account_id=CUSTOMER_X_ACCOUNT,
                        debtor_target_account_id=CUSTOMER_Y_ACCOUNT,
                        denomination=parameters.TEST_DENOMINATION,
                    ),
                ],
                expected_balances_at_ts={
                    start_datetime
                    + timedelta(minutes=3): {
                        CUSTOMER_X_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "150")],
                        CUSTOMER_Y_ACCOUNT: [(SGD_DEFAULT_DIMENSIONS, "50")],
                    }
                },
            ),
        ]

        test_scenario = self.get_simulation_test_scenario(
            start=start_datetime,
            end=end_datetime,
            sub_tests=sub_tests,
        )
        self.run_test_scenario(test_scenario)
