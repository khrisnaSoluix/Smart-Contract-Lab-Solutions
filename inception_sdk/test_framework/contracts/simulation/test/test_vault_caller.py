# standard libs
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

# contracts api
from contracts_api import DateShape, DenominationShape, NumberShape, StringShape

# inception sdk
from inception_sdk.test_framework.common.balance_helpers import BalanceDimensions
from inception_sdk.test_framework.contracts.files import EMPTY_LIABILITY_CONTRACT
from inception_sdk.test_framework.contracts.simulation.data_objects.data_objects import (
    AccountConfig,
    ContractConfig,
    ContractModuleConfig,
    ExpectedRejection,
    ExpectedSchedule,
    SimulationTestScenario,
    SubTest,
    SupervisorConfig,
)
from inception_sdk.test_framework.contracts.simulation.helper import (
    account_to_simulate,
    create_account_instruction,
    create_account_plan_assoc_instruction,
    create_account_product_version_update_instruction,
    create_calendar,
    create_calendar_event,
    create_custom_instruction,
    create_flag_event,
    create_global_parameter_instruction,
    create_global_parameter_value_instruction,
    create_inbound_hard_settlement_instruction,
    create_outbound_hard_settlement_instruction,
    create_plan_instruction,
    create_transfer_instruction,
    update_account_status_pending_closure,
)
from inception_sdk.test_framework.contracts.simulation.utils import (
    SimulationTestCase,
    get_account_logs,
    get_balances,
    get_derived_parameters,
    get_flag_created,
    get_flag_definition_created,
    get_logs,
    get_logs_with_timestamp,
    get_module_link_created,
    get_num_postings,
    get_plan_assoc_created,
)

# Note: A new test config is created with sufficient permissions to access the
#  </core_api.v1.contracts.CoreAPIContracts/SimulateContracts> endpoint
basepath = "inception_sdk/test_framework/contracts/simulation/test"
contract_modules_basepath = "inception_sdk/test_framework/common/contract_modules_examples"
CONTRACT_FULL_FILE = basepath + "/mock_product/full_contract.py"
CONTRACT_FULL_UPDATED_VERSION_FILE = basepath + "/mock_product/full_contract_updated_version.py"
CONTRACT_WITH_SHARED_FUNCTION_FILE = (
    contract_modules_basepath + "/full_contract_with_shared_function.py"
)
CHECKING_CONTRACT_FILE = basepath + "/mock_product/supervised_checking_account.py"
CHECKING_CONTRACT_WITH_MODULES_FILE = (
    basepath + "/mock_product/supervised_checking_account_with_contract_modules.py"
)
SAVINGS_CONTRACT_FILE = basepath + "/mock_product/supervised_savings_deposit_account.py"
SAVINGS_CONTRACT_WITH_MODULES_FILE = (
    basepath + "/mock_product/supervised_savings_deposit_account_with_contract_modules.py"
)
YOUTH_CONTRACT_FILE = basepath + "/mock_product/supervised_youth_account.py"
SUPERVISOR_CONTRACT_FILE = basepath + "/mock_product/supervisor_contract.py"
DEFAULT_CLIENT_BATCH_ID = str(uuid.uuid4())

CONTRACT_MODULES_ALIAS_FILE_MAP_MULTIPLE = {
    "interest": contract_modules_basepath + "/contract_module.py",
    "module_2": contract_modules_basepath + "/contract_module_2.py",
}

CONTRACT_MODULES_ALIAS_FILE_MAP_SINGLE = {
    "interest": contract_modules_basepath + "/contract_module.py",
}


class ClientTest(SimulationTestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract_empty = EMPTY_LIABILITY_CONTRACT
        cls.contract_full = CONTRACT_FULL_FILE
        cls.contract_full_updated_version = CONTRACT_FULL_UPDATED_VERSION_FILE
        cls.contract_with_contract_module = CONTRACT_WITH_SHARED_FUNCTION_FILE
        cls.checking_contract = CHECKING_CONTRACT_FILE
        cls.checking_contract_with_modules = CHECKING_CONTRACT_WITH_MODULES_FILE
        cls.savings_contract_with_modules = SAVINGS_CONTRACT_WITH_MODULES_FILE
        cls.savings_contract = SAVINGS_CONTRACT_FILE
        cls.youth_contract = YOUTH_CONTRACT_FILE
        supervisor_contract = SUPERVISOR_CONTRACT_FILE

        with open(supervisor_contract, encoding="utf-8") as smart_contract_file:
            cls.supervisor_contract_contents = smart_contract_file.read()

        cls.load_test_config()

    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at
        # Uncomment this for timing info.
        print("{} ({}s)".format(self.id().rpartition(".")[2], round(self._elapsed_time, 2)))

    def test_unchallenged_deposit(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        template_params = {}
        instance_params = {}

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            instance_params=instance_params,
            template_params=template_params,
            contract_file_path=self.contract_empty,
        )

        events = []

        events.append(
            create_inbound_hard_settlement_instruction(
                amount="1000",
                event_datetime=start,
                denomination="GBP",
                client_transaction_id="123456",
                instruction_details={"description": "test2"},
                batch_details={"description": "test"},
                client_batch_id="123",
            )
        )

        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            account_creation_events=[main_account],
            internal_account_ids=["1"],
        )

        self.assertEqual(get_num_postings(res), 1)

    def test_wrong_denomination_with_parameter_deposit(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        template_params = {
            "denomination": "GBP",
            "overdraft_limit": "0",
            "overdraft_fee": "0",
            "gross_interest_rate": "0",
        }
        instance_params = {"interest_payment_day": "1"}

        events = []

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            instance_params=instance_params,
            template_params=template_params,
            contract_file_path=self.contract_full,
        )

        events.append(
            create_inbound_hard_settlement_instruction(
                amount="1000",
                event_datetime=start,
                denomination="EUR",
                client_transaction_id="Visa",
                instruction_details={"description": "test2"},
                batch_details={"description": "test"},
                client_batch_id="123",
            )
        )

        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            account_creation_events=[main_account],
            internal_account_ids=["1"],
        )
        # No valid postings were made
        self.assertEqual(get_num_postings(res), 0)
        # The event log contains the error we expect to be raised by an invalid currency
        self.assertIn(
            "Cannot make transactions in given denomination; transactions must be in GBP",
            get_account_logs(res),
        )

    def test_fee_applied_after_withdrawal(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        template_params = {
            "denomination": "GBP",
            "overdraft_limit": "100",
            "overdraft_fee": "20",
            "gross_interest_rate": "0",
        }
        instance_params = {"interest_payment_day": "1"}

        events = []
        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            instance_params=instance_params,
            template_params=template_params,
            contract_file_path=self.contract_full,
        )

        events.append(
            create_outbound_hard_settlement_instruction(
                amount="110",
                event_datetime=start,
                denomination="GBP",
                client_transaction_id="123456",
                instruction_details={"description": "test2"},
                batch_details={"description": "test"},
                client_batch_id="123",
            )
        )

        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            account_creation_events=[main_account],
            internal_account_ids=["1"],
        )
        balances = get_balances(res)["Main account"]
        self.assertEqual(balances.at(start)[BalanceDimensions()].net, -110)
        self.assertEqual(balances.latest()[BalanceDimensions()].net, -130)

    def test_supervisor_contract(self):
        # this test provides output for sample_supervisor_response
        start = datetime(year=2020, month=5, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=7, day=1, tzinfo=timezone.utc)

        youth_template_params = {"denomination": "USD", "zero_bal_timeout": "10"}

        youth_instance_params = {"statement_day": "1", "orphaned": "no"}

        checking_template_params = {
            "denomination": "USD",
            "maintenance_fee": "25.00",
            "internal_maintenance_fee_account": "1",
            "minimum_daily_checking_balance": "1500.00",
            "minimum_combined_balance": "5000.00",
            "minimum_monthly_deposit": "1000.00",
            "overdraft_fee": "10.00",
            "internal_overdraft_fee_account": "1",
            "overdraft_fee_accrual": "NO",
            "overdraft_buffer": "0.00",
        }
        checking_instance_params = {
            "overdraft_limit": "2000",
            "debit_card_coverage": "YES",
            "maintenance_fee_check_day": "28",
        }

        savings_instance_params = {"interest_application_day": "5"}
        savings_template_params = {
            "denomination": "USD",
            # 'gross_interest_rate': '0.149',
            "gross_interest_rate_tiers": json.dumps(
                {"high": "0.15", "medium": "0.10", "low": "0.01", "DEFAULT": "0.149"}
            ),
            "minimum_deposit": "0.01",
            "maximum_daily_deposit": "1000",
            "minimum_withdrawal": "0.01",
            "maximum_daily_withdrawal": "1000",
            "maximum_balance": "10000",
            "monthly_transaction_hard_limit": "6",
            "monthly_transaction_soft_limit": "5",
            "monthly_transaction_notification_limit": "4",
            "monthly_transaction_charge": "15",
            "promotion_rate": "0",
            "check_hold_percentage_tiers": json.dumps(
                {
                    "customer_tier_high": "0.40",
                    "customer_tier_medium": "0.50",
                    "customer_tier_low": "0.60",
                    "DEFAULT": "0.60",
                }
            ),
        }

        events = []

        checking_account = account_to_simulate(
            timestamp=start,
            account_id="Checking Account",
            # IDs need to align with supervisor, these can't be autogenerated
            contract_version_id="1",
            instance_params=checking_instance_params,
            template_params=checking_template_params,
            contract_file_path=self.checking_contract,
        )
        savings_account = account_to_simulate(
            timestamp=start,
            account_id="Savings Account",
            # IDs need to align with supervisor, these can't be autogenerated
            contract_version_id="2",
            instance_params=savings_instance_params,
            template_params=savings_template_params,
            contract_file_path=self.savings_contract,
        )
        youth_account = account_to_simulate(
            timestamp=start,
            account_id="Youth Account",
            # IDs need to align with supervisor, these can't be autogenerated
            contract_version_id="3",
            instance_params=youth_instance_params,
            template_params=youth_template_params,
            contract_file_path=self.youth_contract,
        )

        # To see balances on both checking and saving account
        events.append(
            create_inbound_hard_settlement_instruction(
                "900",
                start + timedelta(days=10),
                denomination="USD",
                target_account_id="Savings Account",
                client_transaction_id="123456",
                instruction_details={"description": "test2"},
                batch_details={"description": "test"},
                client_batch_id="123",
            )
        )

        # Create plan
        events.append(
            create_plan_instruction(
                timestamp=start + timedelta(days=11),
                plan_id="1",
                supervisor_contract_version_id="116",
            )
        )

        # Create plan assoc
        events.append(
            create_account_plan_assoc_instruction(
                timestamp=start + timedelta(days=11),
                assoc_id="Supervised checking account",
                account_id="Checking Account",
                plan_id="1",
            )
        )

        events.append(
            create_account_plan_assoc_instruction(
                timestamp=start + timedelta(days=11),
                assoc_id="Supervised savings account",
                account_id="Savings Account",
                plan_id="1",
            )
        )

        res = self.client.simulate_smart_contract(
            supervisor_contract_code=self.supervisor_contract_contents,
            supervisee_version_id_mapping={
                "checking": "1",
                "savings": "2",
                "youth": "3",
            },
            supervisor_contract_version_id="116",
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            account_creation_events=[savings_account, checking_account, youth_account],
            internal_account_ids=["1"],
        )

        self.assertEqual(get_num_postings(res, "Savings Account"), 2)
        self.assertEqual(get_num_postings(res, "Checking Account"), 2)
        self.assertEqual(get_num_postings(res, "Main account"), 0)
        self.assertEqual(get_num_postings(res, "1"), 4)

    def test_supervisor_contract_no_mapping(self):
        # this test checks validation for supervisor tests with missing mappings
        start = datetime(year=2020, month=5, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=7, day=1, tzinfo=timezone.utc)
        with self.assertRaises(ValueError) as ctx:
            self.client.simulate_smart_contract(
                supervisor_contract_code=self.supervisor_contract_contents,
                supervisee_version_id_mapping=None,
                supervisor_contract_version_id="116",
                start_timestamp=start,
                end_timestamp=end,
                events=[],
            )
        self.assertEqual(
            ctx.exception.args[0],
            "supervisee_version_id_mapping missing or empty for a test using "
            "supervisor_contract_code",
        )

    def test_wrong_denomination_deposit(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        template_params = {
            "denomination": "GBP",
            "overdraft_limit": "0",
            "overdraft_fee": "0",
            "gross_interest_rate": "0",
        }
        instance_params = {"interest_payment_day": "1"}
        events = []

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            instance_params=instance_params,
            template_params=template_params,
            contract_file_path=self.contract_full,
        )

        events.append(
            create_inbound_hard_settlement_instruction(
                amount="1000",
                event_datetime=start,
                denomination="EUR",
                client_transaction_id="123456",
                instruction_details={"description": "test2"},
                batch_details={"description": "test"},
                client_batch_id="123",
            )
        )
        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            account_creation_events=[main_account],
            internal_account_ids=["1"],
        )

        # No valid postings were made
        self.assertEqual(get_num_postings(res), 0)
        # The event log contains the error we expect to be raised by an invalid currency
        self.assertIn(
            'account "Main account" rejected with rejection type "WrongDenomination"'
            ' and reason "Cannot make transactions in given denomination;'
            ' transactions must be in GBP"',
            get_account_logs(res),
        )

    def test_set_flag(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        template_params = {
            "denomination": "GBP",
            "overdraft_limit": "0",
            "overdraft_fee": "0",
            "gross_interest_rate": "0",
        }
        instance_params = {"interest_payment_day": "1"}

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            instance_params=instance_params,
            template_params=template_params,
            contract_file_path=self.contract_full,
        )

        events = []
        events.append(
            create_flag_event(
                flag_definition_id="1",
                timestamp=start,
                expiry_timestamp=end,
                account_id="Main account",
            )
        )

        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            account_creation_events=[main_account],
            flag_definition_ids=["1"],
        )

        # successfully create flag definition
        result_logs = get_logs(res)
        account_logs = get_account_logs(res)
        self.assertIn('created flag definition "1"', result_logs)

        flag_definition_created = get_flag_definition_created(res, "1")
        self.assertTrue(flag_definition_created)

        # successfully create flag for main account
        self.assertIn('created flag with definition "1" for account "Main account"', account_logs)

        flag_created = get_flag_created(res, "1")
        self.assertTrue(flag_created)

    def test_single_response(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        events = []

        # simulate_smart_contracts already has 1 event defined by default
        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            internal_account_ids=["1"],
        )

        self.assertEqual(len(res), 1)

        logs = get_logs(res)
        self.assertIn('created account "1"', logs)

    def test_large_response(self):
        # this test provides output for sample_simulator_response
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=3, day=2, tzinfo=timezone.utc)
        template_params = {
            "denomination": "GBP",
            "overdraft_limit": "100",
            "overdraft_fee": "20",
            "gross_interest_rate": "0",
        }
        instance_params = {"interest_payment_day": "1"}

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            instance_params=instance_params,
            template_params=template_params,
            contract_file_path=self.contract_full,
        )

        events = []

        events.append(
            create_outbound_hard_settlement_instruction(
                amount="110",
                event_datetime=start,
                denomination="GBP",
                client_transaction_id="123456",
                instruction_details={"description": "test2"},
                batch_details={"description": "test"},
                client_batch_id="123",
            )
        )

        events.append(
            create_flag_event(
                flag_definition_id="debug_flag",
                timestamp=start,
                expiry_timestamp=start + timedelta(days=5),
                account_id="Main account",
            )
        )

        events.append(
            create_inbound_hard_settlement_instruction(
                amount="1000",
                event_datetime=start + timedelta(days=10),
                denomination="GBP",
                client_transaction_id="Visa2",
                instruction_details={"description": "test2"},
                batch_details={"description": "test"},
                client_batch_id="1232",
            )
        )

        events.append(
            create_inbound_hard_settlement_instruction(
                amount="350",
                event_datetime=start + timedelta(days=20),
                denomination="EUR",
                client_transaction_id="Visa3",
                instruction_details={"description": "test2"},
                batch_details={"description": "test"},
                client_batch_id="1233",
            )
        )

        events.append(
            create_inbound_hard_settlement_instruction(
                amount="160",
                event_datetime=start + timedelta(days=30),
                denomination="GBP",
                client_transaction_id="Visa4",
                instruction_details={"description": "test2"},
                batch_details={"description": "test"},
                client_batch_id="1234",
            )
        )

        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            account_creation_events=[main_account],
            internal_account_ids=["1"],
            flag_definition_ids=["debug_flag"],
        )

        balances = get_balances(res)["Main account"]
        self.assertEqual(balances.at(start)[BalanceDimensions()].net, -110)
        self.assertEqual(balances.latest()[BalanceDimensions()].net, 1030)

    def test_manual_event(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            contract_file_path=self.contract_empty,
        )

        template_params = {
            "denomination": "GBP",
            "overdraft_limit": "100",
            "overdraft_fee": "20",
            "gross_interest_rate": "0",
        }
        instance_params = {"interest_payment_day": "1"}

        manual_account = account_to_simulate(
            timestamp=start + timedelta(minutes=5),
            account_id="Manual account",
            instance_params=instance_params,
            template_params=template_params,
            contract_file_path=self.contract_full,
            create_account=False,
        )

        events = []

        events.append(
            create_inbound_hard_settlement_instruction(
                amount="1000",
                event_datetime=start,
                denomination="GBP",
                client_transaction_id="123456",
                instruction_details={"description": "test2"},
                batch_details={"description": "test"},
                client_batch_id="123",
            )
        )

        events.append(
            create_account_instruction(
                timestamp=manual_account["timestamp"],
                account_id=manual_account["account_id"],
                product_id=manual_account["smart_contract_version_id"],
                instance_param_vals=manual_account["instance_parameters"],
            )
        )

        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            smart_contract_version_ids=[manual_account["smart_contract_version_id"]],
            templates_parameters=[manual_account["template_parameters"]],
            contract_codes=[manual_account["contract_file_contents"]],
            account_creation_events=[main_account],
            internal_account_ids=["1"],
        )

        self.assertIn('created account "Manual account"', get_account_logs(res, "Manual account"))
        self.assertEqual(get_num_postings(res), 1)

    def test_failed_response(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            contract_file_path=self.contract_empty,
        )

        events = []

        events.append(
            create_inbound_hard_settlement_instruction(
                amount="1000",
                event_datetime=start,
                denomination="GBP",
                client_transaction_id="123456",
                instruction_details={"description": "test2"},
                batch_details={"description": "test"},
                client_batch_id="123",
                target_account_id="Non existent account",
            )
        )

        with self.assertRaises(ValueError) as ex:
            self.client.simulate_smart_contract(
                start_timestamp=start,
                end_timestamp=end,
                events=events,
                account_creation_events=[main_account],
                internal_account_ids=["1"],
            )

        self.assertIn('account ID "Non existent account"', str(ex.exception))

    def test_posting_instructions(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        main_account = account_to_simulate(start, "Main account")

        events = [
            create_inbound_hard_settlement_instruction(
                amount="1",
                event_datetime=start + timedelta(minutes=1),
                denomination="GBP",
                client_transaction_id="IHS_POSTING",
                instruction_details={"description": "IHS"},
                batch_details={"description": "IHS_BATCH_DETAILS"},
                client_batch_id="IHS_BATCH_ID",
            ),
            create_outbound_hard_settlement_instruction(
                amount="1",
                event_datetime=start + timedelta(minutes=2),
                denomination="GBP",
                client_transaction_id="OHS_POSTING",
                instruction_details={"description": "OHS"},
                batch_details={"description": "OHS_BATCH_DETAILS"},
                client_batch_id="OHS_BATCH_ID",
            ),
            create_transfer_instruction(
                amount="2",
                creditor_target_account_id="Main account",
                debtor_target_account_id="2",
                event_datetime=start + timedelta(minutes=3),
                denomination="GBP",
                client_transaction_id="TRANSFER_POSTING",
                instruction_details={"description": "TRANSFER"},
                batch_details={"description": "TRANSFER_BATCH_DETAILS"},
                client_batch_id="TRANSFER_BATCH_ID",
            ),
            create_custom_instruction(
                amount="3",
                creditor_target_account_id="Main account",
                debtor_target_account_id="2",
                creditor_target_account_address="DEFAULT",
                debtor_target_account_address="DEFAULT",
                event_datetime=start + timedelta(minutes=4),
                denomination="GBP",
                client_transaction_id="CUSTOM_INSTRUCTION_POSTING",
                instruction_details={"description": "CUSTOM_INSTRUCTION"},
                batch_details={"description": "CUSTOM_INSTRUCTION_BATCH_DETAILS"},
                client_batch_id="CUSTOM_INSTRUCTION_BATCH_ID",
            ),
        ]

        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            internal_account_ids=["1", "2"],
            account_creation_events=[main_account],
        )

        self.assertEqual(get_num_postings(res, "Main account"), 4)
        self.assertEqual(get_num_postings(res, "2"), 2)

        balances = get_balances(res)
        main_balances = balances["Main account"]
        internal_balances = balances["2"]
        self.assertEqual(main_balances.at(start + timedelta(minutes=1))[BalanceDimensions()].net, 1)
        self.assertEqual(main_balances.at(start + timedelta(minutes=2))[BalanceDimensions()].net, 0)
        self.assertEqual(main_balances.at(start + timedelta(minutes=3))[BalanceDimensions()].net, 2)
        self.assertEqual(main_balances.at(start + timedelta(minutes=4))[BalanceDimensions()].net, 5)
        self.assertEqual(
            internal_balances.at(start + timedelta(minutes=5))[BalanceDimensions()].net,
            -5,
        )

    def test_derived_parameters(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        template_params = {
            "denomination": "GBP",
            "overdraft_limit": "0",
            "overdraft_fee": "0",
            "gross_interest_rate": "0",
        }
        instance_params = {"interest_payment_day": "1"}

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            instance_params=instance_params,
            template_params=template_params,
            contract_file_path=self.contract_full,
        )

        events = []

        events.append(
            create_inbound_hard_settlement_instruction(
                amount="1000",
                event_datetime=start,
                denomination="GBP",
                client_transaction_id="123456",
                instruction_details={"description": "test2"},
                batch_details={"description": "test"},
                client_batch_id="123",
            )
        )

        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            account_creation_events=[main_account],
            internal_account_ids=["1"],
            output_account_ids=["Main account"],
            output_timestamps=[start],
        )

        # Acceptance criteria:
        # Get the derived parameter
        derived_params = get_derived_parameters(res)["Main account"].at(start)
        self.assertEqual(derived_params["days_past_due"], "10")
        expected_end_date = derived_params["expected_end_date"]
        self.assertEqual(expected_end_date, "2020-12-22")

    def test_query_internal_account_balances(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        main_account = account_to_simulate(start, "Main account")

        events = [
            create_inbound_hard_settlement_instruction(
                amount="1",
                event_datetime=start + timedelta(minutes=1),
                denomination="GBP",
                client_transaction_id="IHS_POSTING_PART_1",
                instruction_details={"description": "IHS"},
                batch_details={"description": "IHS_BATCH_DETAILS"},
                client_batch_id="IHS_BATCH_ID_PART_1",
                internal_account_id="internal_asset_account_1",
            ),
            create_outbound_hard_settlement_instruction(
                amount="2",
                event_datetime=start + timedelta(minutes=2),
                denomination="GBP",
                client_transaction_id="OHS_POSTING_PART_1",
                instruction_details={"description": "OHS"},
                batch_details={"description": "OHS_BATCH_DETAILS"},
                client_batch_id="OHS_BATCH_ID_PART_1",
                internal_account_id="internal_asset_account_2",
            ),
            create_transfer_instruction(
                amount="3",
                creditor_target_account_id="Main account",
                debtor_target_account_id="internal_asset_account_3",
                event_datetime=start + timedelta(minutes=3),
                denomination="GBP",
                client_transaction_id="TRANSFER_POSTING_PART_1",
                instruction_details={"description": "TRANSFER"},
                batch_details={"description": "TRANSFER_BATCH_DETAILS"},
                client_batch_id="TRANSFER_BATCH_ID_PART_1",
            ),
            create_inbound_hard_settlement_instruction(
                amount="4",
                event_datetime=start + timedelta(minutes=4),
                denomination="GBP",
                client_transaction_id="IHS_POSTING_PART_2",
                instruction_details={"description": "IHS"},
                batch_details={"description": "IHS_BATCH_DETAILS"},
                client_batch_id="IHS_BATCH_ID_PART_2",
                internal_account_id="internal_liability_account_1",
            ),
            create_outbound_hard_settlement_instruction(
                amount="5",
                event_datetime=start + timedelta(minutes=5),
                denomination="GBP",
                client_transaction_id="OHS_POSTING_PART_2",
                instruction_details={"description": "OHS"},
                batch_details={"description": "OHS_BATCH_DETAILS"},
                client_batch_id="OHS_BATCH_ID_PART_2",
                internal_account_id="internal_liability_account_2",
            ),
            create_transfer_instruction(
                amount="6",
                creditor_target_account_id="Main account",
                debtor_target_account_id="internal_liability_account_3",
                event_datetime=start + timedelta(minutes=6),
                denomination="GBP",
                client_transaction_id="TRANSFER_POSTING_PART_2",
                instruction_details={"description": "TRANSFER"},
                batch_details={"description": "TRANSFER_BATCH_DETAILS"},
                client_batch_id="TRANSFER_BATCH_ID_PART_2",
            ),
        ]

        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            internal_account_ids={
                "internal_asset_account_1": "ASSET",
                "internal_asset_account_2": "ASSET",
                "internal_asset_account_3": "ASSET",
                "internal_liability_account_1": "LIABILITY",
                "internal_liability_account_2": "LIABILITY",
                "internal_liability_account_3": "LIABILITY",
            },
            account_creation_events=[main_account],
        )

        self.assertEqual(get_num_postings(res, "Main account"), 6)
        balances = get_balances(res)
        self.assertEqual(balances["internal_asset_account_1"].latest()[BalanceDimensions()].net, 1)
        self.assertEqual(balances["internal_asset_account_2"].latest()[BalanceDimensions()].net, -2)
        self.assertEqual(balances["internal_asset_account_3"].latest()[BalanceDimensions()].net, 3)
        self.assertEqual(
            balances["internal_liability_account_1"].latest()[BalanceDimensions()].net,
            -4,
        )
        self.assertEqual(
            balances["internal_liability_account_2"].latest()[BalanceDimensions()].net,
            5,
        )
        self.assertEqual(
            balances["internal_liability_account_3"].latest()[BalanceDimensions()].net,
            -6,
        )

    def test_create_calendar_and_events(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            contract_file_path=self.contract_empty,
        )

        events = []
        events.extend(
            [
                create_calendar(
                    timestamp=start,
                    calendar_id="TEST_CALENDAR",
                ),
                create_calendar_event(
                    timestamp=start,
                    calendar_event_id="TEST_EVENT",
                    calendar_id="TEST_CALENDAR",
                    start_timestamp=start,
                    end_timestamp=end,
                ),
            ]
        )

        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            account_creation_events=[main_account],
        )
        result_logs = get_logs(res)
        # Successfully create calendar
        self.assertIn('created calendar with id "TEST_CALENDAR"', result_logs)
        # Successfully create calendar event
        self.assertIn('created calendar event for calendar "TEST_CALENDAR"', result_logs)

    def test_check_posting_rejections(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = start + timedelta(hours=5)
        template_params = {
            "denomination": "GBP",
            "overdraft_limit": "0",
            "overdraft_fee": "0",
            "gross_interest_rate": "0",
        }
        instance_params = {"interest_payment_day": "1"}

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            instance_params=instance_params,
            template_params=template_params,
            contract_file_path=self.contract_full,
        )
        events = [
            create_inbound_hard_settlement_instruction(
                event_datetime=start + timedelta(hours=1),
                target_account_id="Main account",
                amount="1000",
                denomination="USD",
            )
        ]
        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            account_creation_events=[main_account],
            internal_account_ids=["1"],
        )

        logs_with_timestamp = get_logs_with_timestamp(res)
        rejection_time = start + timedelta(hours=1)
        account_id = "Main account"
        rejection_type = "WrongDenomination"
        rejection_reason = (
            "Cannot make transactions in given denomination; " "transactions must be in GBP"
        )
        msg = "cannot find rejected postings with"

        expected_rejections = [
            ExpectedRejection(
                timestamp=rejection_time,
                account_id=account_id,
                rejection_type=rejection_type,
                rejection_reason=rejection_reason,
            )
        ]
        self.check_posting_rejections(expected_rejections, logs_with_timestamp)

        rejections_with_wrong_time = [
            ExpectedRejection(
                timestamp=datetime(year=2021, month=1, day=1, hour=3, tzinfo=timezone.utc),
                account_id=account_id,
                rejection_type=rejection_type,
                rejection_reason=rejection_reason,
            )
        ]

        with self.assertRaises(AssertionError) as ex:
            self.check_posting_rejections(rejections_with_wrong_time, logs_with_timestamp, msg)

        self.assertIn(f"{msg}: {rejections_with_wrong_time}", str(ex.exception))

        false_rejections = [
            # rejection_with_wrong_type
            ExpectedRejection(
                timestamp=rejection_time,
                account_id=account_id,
                rejection_type="Bagels",
                rejection_reason=rejection_reason,
            ),
            # rejection_with_wrong_reason
            ExpectedRejection(
                timestamp=rejection_time,
                account_id=account_id,
                rejection_type=rejection_type,
                rejection_reason="Too many bagels",
            ),
            # rejection_with_wrong_account
            ExpectedRejection(
                timestamp=rejection_time,
                account_id="Wrong account",
                rejection_type=rejection_type,
                rejection_reason=rejection_reason,
            ),
        ]

        with self.assertRaises(AssertionError) as ex:
            self.check_posting_rejections(false_rejections, logs_with_timestamp, msg)

        self.assertIn(f"{msg}: {false_rejections}", str(ex.exception))

    def test_check_schedule_processed(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = start + timedelta(days=1, hours=5)
        template_params = {
            "denomination": "GBP",
            "overdraft_limit": "0",
            "overdraft_fee": "0",
            "gross_interest_rate": "0",
        }
        instance_params = {"interest_payment_day": "1"}

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            instance_params=instance_params,
            template_params=template_params,
            contract_file_path=self.contract_full,
        )
        events = [
            create_inbound_hard_settlement_instruction(
                event_datetime=start + timedelta(hours=1),
                target_account_id="Main account",
                amount="1000",
                denomination="USD",
            )
        ]
        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            account_creation_events=[main_account],
            internal_account_ids=["1"],
        )

        scheduled_time = datetime(year=2021, month=1, day=2, tzinfo=timezone.utc)
        event_id = "ACCRUE_INTEREST"
        account_id = "Main account"
        msg = "cannot find processed schedule with"

        expected_schedule_runs = [
            ExpectedSchedule(
                run_times=[start, scheduled_time],
                event_id=event_id,
                account_id=account_id,
                count=2,
            )
        ]
        self.check_schedule_processed(expected_schedule_runs, res)

        schedule_runs_with_wrong_time = [
            ExpectedSchedule(
                run_times=[datetime(year=2021, month=1, day=1, hour=3, tzinfo=timezone.utc)],
                event_id=event_id,
                account_id=account_id,
            )
        ]

        with self.assertRaises(AssertionError) as ex:
            self.check_schedule_processed(schedule_runs_with_wrong_time, res, msg)

        self.assertIn(
            f"{msg}: {[datetime(year=2021, month=1, day=1, hour=3, tzinfo=timezone.utc)]}",
            str(ex.exception),
        )

        false_schedule_runs = [
            # wrong account
            ExpectedSchedule(
                run_times=[scheduled_time],
                event_id=event_id,
                account_id="Wrong account",
            ),
            # wrong event
            ExpectedSchedule(
                run_times=[scheduled_time],
                event_id="LOSING_INTEREST",
                account_id=account_id,
            ),
        ]

        with self.assertRaises(AssertionError) as ex:
            self.check_schedule_processed(false_schedule_runs, res, msg)

        self.assertIn(f"{msg}: {[scheduled_time, scheduled_time]}", str(ex.exception))

    def test_account_update_close_triggers_close_code_outstanding_balance(self):
        start = datetime(year=2019, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2019, month=1, day=2, tzinfo=timezone.utc)
        template_params = {
            "denomination": "GBP",
            "overdraft_limit": "0",
            "overdraft_fee": "10",
            "gross_interest_rate": "0",
        }
        instance_params = {"interest_payment_day": "1"}

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            instance_params=instance_params,
            template_params=template_params,
            contract_file_path=self.contract_full,
        )

        events = []

        events.append(
            create_outbound_hard_settlement_instruction(
                amount="110",
                event_datetime=start,
                denomination="GBP",
                client_transaction_id="123456",
                instruction_details={"description": "test2"},
                batch_details={"description": "test"},
                client_batch_id="123",
            )
        )

        events.append(
            update_account_status_pending_closure(
                timestamp=(start + timedelta(minutes=10)), account_id="Main account"
            )
        )

        with self.assertRaises(ValueError) as ex:
            self.client.simulate_smart_contract(
                start_timestamp=start,
                end_timestamp=end,
                events=events,
                account_creation_events=[main_account],
                internal_account_ids=["1"],
                debug=True,
            )

        self.assertIn("Cannot close account until account balance nets to 0", str(ex.exception))

    def test_global_parameter(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=2, tzinfo=timezone.utc)
        template_params = {
            "denomination": "GBP",
            "overdraft_limit": "0",
            "overdraft_fee": "0",
            "gross_interest_rate": "0",
        }
        instance_params = {"interest_payment_day": "1"}

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            instance_params=instance_params,
            template_params=template_params,
            contract_file_path=self.contract_full,
        )

        events = [
            create_global_parameter_instruction(
                timestamp=start,
                global_parameter_id="global_interest_rate",
                display_name="Global yearly interest rate",
                description="Global yearly interest rate",
                number=NumberShape(),
                initial_value="1.20491",
            ),
            create_global_parameter_value_instruction(
                timestamp=start,
                global_parameter_id="global_interest_rate",
                value="1.20493",
                effective_timestamp=start + timedelta(hours=1),
            ),
            create_global_parameter_instruction(
                timestamp=start + timedelta(hours=2),
                global_parameter_id="denomination",
                display_name="Denomination",
                description="Denomination",
                denomination=DenominationShape(permitted_denominations=["GBP"]),
                initial_value="GBP",
            ),
            create_global_parameter_instruction(
                timestamp=start + timedelta(hours=3),
                global_parameter_id="example_str_parameter",
                display_name="Example str parameter",
                description="Example str parameter",
                str=StringShape(),
                initial_value="Example str",
            ),
            create_global_parameter_instruction(
                timestamp=start + timedelta(hours=4),
                global_parameter_id="example_date_parameter",
                display_name="Example date parameter",
                description="Example date parameter",
                date=DateShape(),
                initial_value=start + timedelta(hours=5),
            ),
        ]

        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            account_creation_events=[main_account],
        )

        result_logs = get_logs(res)
        # successfully created global parameter of type "number"
        self.assertIn('created global parameter "global_interest_rate"', result_logs)

        # successfully initiated global parameter value
        self.assertIn(
            'created value "1.20491" for global parameter "global_interest_rate"',
            result_logs,
        )

        # successfully updated global parameter value
        self.assertIn(
            'created value "1.20493" for global parameter "global_interest_rate"',
            result_logs,
        )

        # successfully created global parameter of type "denomination"
        self.assertIn('created global parameter "denomination"', result_logs)

        # successfully initiated global parameter value
        self.assertIn(
            'created value "GBP" for global parameter "denomination"',
            result_logs,
        )

        # successfully created global parameter of type "str"
        self.assertIn('created global parameter "example_str_parameter"', result_logs)

        # successfully initiated global parameter value
        self.assertIn(
            'created value "Example str" for global parameter "example_str_parameter"',
            result_logs,
        )

        # successfully created global parameter of type "date"
        self.assertIn('created global parameter "example_date_parameter"', result_logs)

        # successfully initiated global parameter value
        self.assertIn(
            'created value "2021-01-01 05:00:00+00:00"'
            ' for global parameter "example_date_parameter"',
            result_logs,
        )

    def test_account_product_version_update_triggers_upgrade_code(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=2, tzinfo=timezone.utc)
        template_params = {
            "denomination": "GBP",
            "overdraft_limit": "0",
            "overdraft_fee": "0",
            "gross_interest_rate": "0",
        }
        instance_params = {"interest_payment_day": "1"}

        with open(self.contract_full, encoding="utf-8") as smart_contract_file:
            contract_full_contents = smart_contract_file.read()
        with open(self.contract_full_updated_version, encoding="utf-8") as smart_contract_file:
            contract_full_updated_version_contents = smart_contract_file.read()

        events = [
            create_account_instruction(
                timestamp=start,
                account_id="Main account",
                product_id="1000",
                instance_param_vals=instance_params,
            ),
            create_account_product_version_update_instruction(
                timestamp=start + timedelta(hours=1),
                account_id="Main account",
                product_version_id="1001",
            ),
        ]
        res = self.client.simulate_smart_contract(
            contract_codes=[
                contract_full_contents,
                contract_full_updated_version_contents,
            ],
            smart_contract_version_ids=["1000", "1001"],
            start_timestamp=start,
            end_timestamp=end,
            templates_parameters=[template_params, template_params],
            events=events,
        )

        self.assertIn(
            'updated account "Main account" smart contract version to "1001"',
            get_account_logs(res),
        )

    def test_contract_module_gets_executed(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=2, tzinfo=timezone.utc)

        template_params = {"denomination": "GBP", "interest_rate": "1"}
        internal_account_id = "1"

        main_account = account_to_simulate(
            timestamp=start,
            account_id="Main account",
            contract_file_path=self.contract_with_contract_module,
            template_params=template_params,
        )

        contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP_MULTIPLE.items()
        ]

        contract_config = ContractConfig(
            contract_file_path=self.contract_with_contract_module,
            template_params=template_params,
            smart_contract_version_id=main_account["smart_contract_version_id"],
            account_configs=[
                AccountConfig(
                    instance_params={},
                    account_id_base="Main account",
                )
            ],
            linked_contract_modules=contract_modules,
        )

        events = [
            create_inbound_hard_settlement_instruction(
                event_datetime=start + timedelta(hours=1),
                target_account_id="Main account",
                amount="1000",
                denomination="GBP",
            ),
        ]

        res = self.client.simulate_smart_contract(
            start_timestamp=start,
            end_timestamp=end,
            events=events,
            account_creation_events=[main_account],
            internal_account_ids=[internal_account_id],
            contract_config=contract_config,
        )

        balances = get_balances(res)

        # if interest gets accrued correctly, the accrued value should be
        # 1/365 = 0.003 (contract module has 3 decimals) * 1000 = 3
        # internal account dispersed 1000 at the beginning, so current value is -997
        self.assertEqual(balances[internal_account_id].latest()[BalanceDimensions()].net, -997)

        self.assertTrue(
            get_module_link_created(
                res,
                ["interest", "module_2"],
                smart_contract_version_id=main_account["smart_contract_version_id"],
            )
        )

    def test_contract_module_scenario(self):
        start = datetime(year=2021, month=1, day=1, tzinfo=timezone.utc)
        end = datetime(year=2021, month=1, day=2, tzinfo=timezone.utc)

        template_params = {"denomination": "GBP", "interest_rate": "1"}
        smart_contract_version_id = "1"
        internal_accounts = {"1": "LIABILITY"}

        contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP_MULTIPLE.items()
        ]

        contract_config = ContractConfig(
            contract_file_path=self.contract_with_contract_module,
            template_params=template_params,
            smart_contract_version_id=smart_contract_version_id,
            account_configs=[
                AccountConfig(
                    instance_params={},
                    account_id_base="Main account",
                )
            ],
            linked_contract_modules=contract_modules,
        )

        deposit_event = create_inbound_hard_settlement_instruction(
            "1000.00", start + timedelta(hours=1), denomination="GBP"
        )

        sub_tests = [
            # if interest gets accrued correctly, the accrued value should be
            # 1/365 = 0.003 (contract module has 3 decimals) * 1000 = 3
            # internal account dispersed 1000 at the beginning, so current value is -997
            SubTest(
                description="accrual check",
                events=[deposit_event],
                expected_balances_at_ts={
                    end: {"1": [(BalanceDimensions(denomination="GBP"), "-997.00")]}
                },
            )
        ]

        test_scenario = SimulationTestScenario(
            start=start,
            end=end,
            sub_tests=sub_tests,
            contract_config=contract_config,
            internal_accounts=internal_accounts,
        )
        res = self.run_test_scenario(test_scenario)

        self.assertTrue(
            get_module_link_created(
                res,
                ["interest", "module_2"],
                smart_contract_version_id="1",
            )
        )

    def test_supervisor_contract_one_supervisee_with_contract_modules(self):
        start = datetime(year=2020, month=5, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=7, day=1, tzinfo=timezone.utc)

        youth_template_params = {"denomination": "USD", "zero_bal_timeout": "10"}

        youth_instance_params = {"statement_day": "1", "orphaned": "no"}

        checking_template_params = {
            "denomination": "USD",
            "maintenance_fee": "25.00",
            "internal_maintenance_fee_account": "1",
            "minimum_daily_checking_balance": "1500.00",
            "minimum_combined_balance": "5000.00",
            "minimum_monthly_deposit": "1000.00",
            "overdraft_fee": "10.00",
            "internal_overdraft_fee_account": "1",
            "overdraft_fee_accrual": "NO",
            "overdraft_buffer": "0.00",
        }
        checking_instance_params = {
            "overdraft_limit": "2000",
            "debit_card_coverage": "YES",
            "maintenance_fee_check_day": "28",
        }

        savings_instance_params = {"interest_application_day": "5"}
        savings_template_params = {
            "denomination": "USD",
            # 'gross_interest_rate': '0.149',
            "gross_interest_rate_tiers": json.dumps(
                {"high": "0.15", "medium": "0.10", "low": "0.01", "DEFAULT": "0.149"}
            ),
            "minimum_deposit": "0.01",
            "maximum_daily_deposit": "1000",
            "minimum_withdrawal": "0.01",
            "maximum_daily_withdrawal": "1000",
            "maximum_balance": "10000",
            "monthly_transaction_hard_limit": "6",
            "monthly_transaction_soft_limit": "5",
            "monthly_transaction_notification_limit": "4",
            "monthly_transaction_charge": "15",
            "promotion_rate": "0",
            "check_hold_percentage_tiers": json.dumps(
                {
                    "customer_tier_high": "0.40",
                    "customer_tier_medium": "0.50",
                    "customer_tier_low": "0.60",
                    "DEFAULT": "0.60",
                }
            ),
        }

        contract_modules = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP_SINGLE.items()
        ]

        ca_account_configs = [
            AccountConfig(
                account_id_base="checking ",
                instance_params=checking_instance_params,
            )
        ]
        ca_account_contract = ContractConfig(
            clu_resource_id="checking",
            contract_file_path=self.checking_contract_with_modules,
            template_params=checking_template_params,
            smart_contract_version_id="1",
            account_configs=ca_account_configs,
            linked_contract_modules=contract_modules,
        )

        sa_account_configs = [
            AccountConfig(
                account_id_base="savings ",
                instance_params=savings_instance_params,
            )
        ]
        sa_account_contract = ContractConfig(
            clu_resource_id="savings",
            contract_file_path=self.savings_contract,
            template_params=savings_template_params,
            smart_contract_version_id="2",
            account_configs=sa_account_configs,
        )

        youth_account_configs = [
            AccountConfig(
                account_id_base="youth ",
                instance_params=youth_instance_params,
            )
        ]
        youth_account_contract = ContractConfig(
            clu_resource_id="youth",
            contract_file_path=self.youth_contract,
            template_params=youth_template_params,
            smart_contract_version_id="3",
            account_configs=youth_account_configs,
        )

        supervisee_contracts = [
            ca_account_contract,
            sa_account_contract,
            youth_account_contract,
        ]
        supervisor_config = SupervisorConfig(
            supervisor_file_path=SUPERVISOR_CONTRACT_FILE,
            supervisee_contracts=supervisee_contracts,
        )

        sub_tests = [
            SubTest(
                description="inbound hard settlement to saving account",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=start + timedelta(days=10),
                        target_account_id="checking 0",
                        internal_account_id="1",
                        denomination="GBP",
                    ),
                ],
            ),
            SubTest(
                description="check balances",
                expected_balances_at_ts={
                    start
                    + timedelta(days=10, hours=1): {
                        "savings 0": [
                            (BalanceDimensions(), "0"),
                        ],
                        "checking 0": [
                            (BalanceDimensions(), "0"),
                        ],
                        "youth 0": [
                            (BalanceDimensions(), "0"),
                        ],
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + timedelta(days=10),
                        account_id="checking 0",
                        rejection_type="WrongDenomination",
                        rejection_reason="Cannot make transactions in given denomination; "
                        "transactions must be in USD",
                    )
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=supervisor_config,
            internal_accounts=["1"],
        )

        res = self.run_test_scenario(test_scenario)

        self.assertTrue(get_plan_assoc_created(res, plan_id="1", account_id="savings 0"))
        self.assertTrue(get_plan_assoc_created(res, plan_id="1", account_id="checking 0"))
        self.assertTrue(get_plan_assoc_created(res, plan_id="1", account_id="youth 0"))
        self.assertTrue(get_module_link_created(res, ["interest"], smart_contract_version_id="1"))

    def test_multiple_supervisees_on_supervisor_plan_with_contract_modules(self):
        start = datetime(year=2020, month=5, day=1, tzinfo=timezone.utc)
        end = datetime(year=2020, month=7, day=1, tzinfo=timezone.utc)

        youth_template_params = {"denomination": "USD", "zero_bal_timeout": "10"}

        youth_instance_params = {"statement_day": "1", "orphaned": "no"}

        checking_template_params = {
            "denomination": "USD",
            "maintenance_fee": "25.00",
            "internal_maintenance_fee_account": "1",
            "minimum_daily_checking_balance": "1500.00",
            "minimum_combined_balance": "5000.00",
            "minimum_monthly_deposit": "1000.00",
            "overdraft_fee": "10.00",
            "internal_overdraft_fee_account": "1",
            "overdraft_fee_accrual": "NO",
            "overdraft_buffer": "0.00",
        }
        checking_instance_params = {
            "overdraft_limit": "2000",
            "debit_card_coverage": "YES",
            "maintenance_fee_check_day": "28",
        }

        savings_instance_params = {"interest_application_day": "5"}
        savings_template_params = {
            "denomination": "USD",
            # 'gross_interest_rate': '0.149',
            "gross_interest_rate_tiers": json.dumps(
                {"high": "0.15", "medium": "0.10", "low": "0.01", "DEFAULT": "0.149"}
            ),
            "minimum_deposit": "0.01",
            "maximum_daily_deposit": "1000",
            "minimum_withdrawal": "0.01",
            "maximum_daily_withdrawal": "1000",
            "maximum_balance": "10000",
            "monthly_transaction_hard_limit": "6",
            "monthly_transaction_soft_limit": "5",
            "monthly_transaction_notification_limit": "4",
            "monthly_transaction_charge": "15",
            "promotion_rate": "0",
            "check_hold_percentage_tiers": json.dumps(
                {
                    "customer_tier_high": "0.40",
                    "customer_tier_medium": "0.50",
                    "customer_tier_low": "0.60",
                    "DEFAULT": "0.60",
                }
            ),
        }

        contract_modules_savings = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP_MULTIPLE.items()
        ]
        contract_modules_checking = [
            ContractModuleConfig(alias, file_path)
            for (alias, file_path) in CONTRACT_MODULES_ALIAS_FILE_MAP_SINGLE.items()
        ]

        ca_account_configs = [
            AccountConfig(
                account_id_base="checking ",
                instance_params=checking_instance_params,
                number_of_accounts=2,
            )
        ]
        ca_account_contract = ContractConfig(
            clu_resource_id="checking",
            contract_file_path=self.checking_contract_with_modules,
            template_params=checking_template_params,
            smart_contract_version_id="1",
            account_configs=ca_account_configs,
            linked_contract_modules=contract_modules_checking,
        )

        sa_account_configs = [
            AccountConfig(
                account_id_base="savings ",
                instance_params=savings_instance_params,
            )
        ]
        sa_account_contract = ContractConfig(
            clu_resource_id="savings",
            contract_file_path=self.savings_contract_with_modules,
            template_params=savings_template_params,
            smart_contract_version_id="2",
            account_configs=sa_account_configs,
            linked_contract_modules=contract_modules_savings,
        )

        youth_account_configs = [
            AccountConfig(
                account_id_base="youth ",
                instance_params=youth_instance_params,
            )
        ]
        youth_account_contract = ContractConfig(
            clu_resource_id="youth",
            contract_file_path=self.youth_contract,
            template_params=youth_template_params,
            smart_contract_version_id="3",
            account_configs=youth_account_configs,
        )

        supervisee_contracts = [
            ca_account_contract,
            sa_account_contract,
            youth_account_contract,
        ]
        supervisor_config = SupervisorConfig(
            supervisor_file_path=SUPERVISOR_CONTRACT_FILE,
            supervisee_contracts=supervisee_contracts,
        )

        sub_tests = [
            SubTest(
                description="inbound hard settlement to accounts",
                events=[
                    create_inbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=start + timedelta(days=10),
                        target_account_id="checking 0",
                        internal_account_id="1",
                        denomination="GBP",
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=start + timedelta(days=10),
                        target_account_id="checking 1",
                        internal_account_id="1",
                        denomination="GBP",
                    ),
                    create_inbound_hard_settlement_instruction(
                        amount="900",
                        event_datetime=start + timedelta(days=10),
                        target_account_id="savings 0",
                        internal_account_id="1",
                        denomination="GBP",
                    ),
                ],
            ),
            SubTest(
                description="check balances",
                expected_balances_at_ts={
                    start
                    + timedelta(days=10, hours=1): {
                        "savings 0": [
                            (BalanceDimensions(), "0"),
                        ],
                        "checking 0": [
                            (BalanceDimensions(), "0"),
                        ],
                        "checking 1": [(BalanceDimensions(), "0")],
                        "youth 0": [
                            (BalanceDimensions(), "0"),
                        ],
                    }
                },
                expected_posting_rejections=[
                    ExpectedRejection(
                        start + timedelta(days=10),
                        account_id="checking 0",
                        rejection_type="WrongDenomination",
                        rejection_reason="Cannot make transactions in given denomination; "
                        "transactions must be in USD",
                    ),
                    ExpectedRejection(
                        start + timedelta(days=10),
                        account_id="checking 1",
                        rejection_type="WrongDenomination",
                        rejection_reason="Cannot make transactions in given denomination; "
                        "transactions must be in USD",
                    ),
                    ExpectedRejection(
                        start + timedelta(days=10),
                        account_id="savings 0",
                        rejection_type="WrongDenomination",
                        rejection_reason="Cannot make transactions in given denomination; "
                        "transactions must be in USD",
                    ),
                ],
            ),
        ]

        test_scenario = SimulationTestScenario(
            sub_tests=sub_tests,
            start=start,
            end=end,
            supervisor_config=supervisor_config,
            internal_accounts=["1"],
        )

        res = self.run_test_scenario(test_scenario)

        self.assertTrue(get_plan_assoc_created(res, plan_id="1", account_id="savings 0"))
        self.assertTrue(get_plan_assoc_created(res, plan_id="1", account_id="checking 0"))
        self.assertTrue(get_plan_assoc_created(res, plan_id="1", account_id="checking 1"))
        self.assertTrue(get_plan_assoc_created(res, plan_id="1", account_id="youth 0"))

        self.assertTrue(get_module_link_created(res, ["interest"], smart_contract_version_id="1"))
        self.assertTrue(
            get_module_link_created(res, ["interest", "module_2"], smart_contract_version_id="2")
        )
