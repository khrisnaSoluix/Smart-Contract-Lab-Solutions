# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard
# standard libs
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_DOWN, ROUND_HALF_UP, Decimal
from unittest.mock import call

# inception sdk
from inception_sdk.test_framework.contracts.unit.common import (
    ContractModuleTest,
    balance_dimensions,
)
from inception_sdk.vault.contracts.types_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    Balance,
    Phase,
)


@dataclass
class PostingInfo:
    amount: Decimal
    tier_name: str = ""
    description: str = ""


# misc
CONTRACT_MODULE_FILE = "library/common/contract_modules/interest.py"

DEFAULT_DENOMINATION = "USD"
HOOK_EXECUTION_ID = "MOCK_HOOK"
DEFAULT_PHASE = Phase.COMMITTED
DEFAULT_DATE = datetime(2019, 1, 1)
ACCRUED_INTEREST_PAYABLE = "ACCRUED_INTEREST_PAYABLE"
ACCRUED_INTEREST_RECEIVABLE = "ACCRUED_INTEREST_RECEIVABLE"
ACCRUED_OVERDRAFT = "ACCRUED_OVERDRAFT"
ACCRUED_OVERDRAFT_PAYABLE = "ACCRUED_OVERDRAFT_PAYABLE"
ACCRUED_OVERDRAFT_RECEIVABLE = "ACCRUED_OVERDRAFT_RECEIVABLE"
ACCRUED_DEPOSIT = "ACCRUED_DEPOSIT"
ACCRUED_DEPOSIT_PAYABLE = "ACCRUED_DEPOSIT_PAYABLE"
ACCRUED_DEPOSIT_RECEIVABLE = "ACCRUED_DEPOSIT_RECEIVABLE"
ACCRUE_INTEREST = "ACCRUE_INTEREST"
APPLY_ACCRUED_INTEREST = "APPLY_ACCRUED_INTEREST"
APPLY_FEE = "APPLY_FEE"
APPLY_CHARGES = "APPLY_CHARGES"
ACCRUED_OVERDRAFT_FEE = "ACCRUED_OVERDRAFT_FEE"
ACCRUED_OVERDRAFT_FEE_PAYABLE = "ACCRUED_OVERDRAFT_FEE_PAYABLE"
ACCRUED_OVERDRAFT_FEE_RECEIVABLE = "ACCRUED_OVERDRAFT_FEE_RECEIVABLE"
CLOSE_ACCOUNT = "CLOSE_ACCOUNT"
INTERNAL_CONTRA = "INTERNAL_CONTRA"
DEFAULT_CHARGE_TYPE = "INTEREST"


def posting_info_equal(a, b) -> bool:
    return a.amount == b.amount and a.description == b.description


def balances_for_current_account(
    dt=DEFAULT_DATE,
    accrued_overdraft=Decimal(0),
    default_balance=Decimal(0),
    accrued_deposit=Decimal(0),
    overdraft_fee=Decimal(0),
    accrued_deposit_payable=Decimal(0),
    accrued_deposit_receivable=Decimal(0),
):

    balance_dict = defaultdict(lambda: Balance(net=Decimal(0)))
    balance_dict[balance_dimensions(denomination=DEFAULT_DENOMINATION)] = Balance(
        net=default_balance
    )
    balance_dict[
        balance_dimensions(denomination=DEFAULT_DENOMINATION, address=ACCRUED_OVERDRAFT)
    ] = Balance(net=accrued_overdraft)
    balance_dict[
        balance_dimensions(denomination=DEFAULT_DENOMINATION, address=ACCRUED_DEPOSIT_PAYABLE)
    ] = Balance(net=accrued_deposit_payable)
    balance_dict[
        balance_dimensions(denomination=DEFAULT_DENOMINATION, address=ACCRUED_DEPOSIT_RECEIVABLE)
    ] = Balance(net=accrued_deposit_receivable)
    balance_dict[
        balance_dimensions(denomination=DEFAULT_DENOMINATION, address=ACCRUED_DEPOSIT)
    ] = Balance(net=accrued_deposit)
    balance_dict[
        balance_dimensions(denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_OUT)
    ] = Balance(net=accrued_overdraft)
    balance_dict[
        balance_dimensions(denomination=DEFAULT_DENOMINATION, phase=Phase.COMMITTED)
    ] = Balance(net=default_balance)
    balance_dict[
        balance_dimensions(denomination=DEFAULT_DENOMINATION, address=ACCRUED_DEPOSIT)
    ] = Balance(net=accrued_deposit)
    balance_dict[
        balance_dimensions(denomination=DEFAULT_DENOMINATION, address=ACCRUED_OVERDRAFT)
    ] = Balance(net=accrued_overdraft)
    balance_dict[
        balance_dimensions(denomination=DEFAULT_DENOMINATION, address=ACCRUED_OVERDRAFT_FEE)
    ] = Balance(net=overdraft_fee)
    balance_dict[
        balance_dimensions(denomination=DEFAULT_DENOMINATION, address=DEFAULT_ADDRESS)
    ] = Balance(net=default_balance)
    return [(dt, balance_dict)]


class InterestModuleTest(ContractModuleTest):
    contract_module_file = CONTRACT_MODULE_FILE

    def setUp(self):
        self._started_at = time.time()

    def tearDown(self):
        self._elapsed_time = time.time() - self._started_at
        print("{} ({}s)".format(self.id().rpartition(".")[2], round(self._elapsed_time, 5)))

    def create_mock(
        self,
        balance_ts=None,
        postings=None,
        creation_date=DEFAULT_DATE,
        client_transaction=None,
        flags=None,
        **kwargs,
    ):
        balance_ts = balance_ts or []
        postings = postings or []
        client_transaction = client_transaction or {}
        flags = flags or []

        params = {
            key: {"value": value}
            for key, value in locals().items()
            if key not in self.locals_to_ignore
        }
        parameter_ts = self.param_map_to_timeseries(params, creation_date)
        return super().create_mock(
            balance_ts=balance_ts,
            parameter_ts=parameter_ts,
            postings=postings,
            creation_date=creation_date,
            client_transaction=client_transaction,
            flags=flags,
            **kwargs,
        )

    def test_construct_payable_receivable_mapping(self):
        mock_vault = self.create_mock()

        test_cases = [
            {
                "description": "Default Values",
                "expected_result": {
                    "payable_address": "",
                    "receivable_address": "",
                    "payable_internal_account": "",
                    "paid_internal_account": "",
                    "receivable_internal_account": "",
                    "received_internal_account": "",
                },
            },
            {
                "description": "No Default Values",
                "payable_address": "_PAYABLE",
                "receivable_address": "_RECEIVABLE",
                "payable_internal_account": "PAYABLE_ACCOUNT",
                "paid_internal_account": "PAID_ACCOUNT",
                "receivable_internal_account": "RECEIVABLE_ACCOUNT",
                "received_internal_account": "RECEIVED_ACCOUNT",
                "expected_result": {
                    "payable_address": "_PAYABLE",
                    "receivable_address": "_RECEIVABLE",
                    "payable_internal_account": "PAYABLE_ACCOUNT",
                    "paid_internal_account": "PAID_ACCOUNT",
                    "receivable_internal_account": "RECEIVABLE_ACCOUNT",
                    "received_internal_account": "RECEIVED_ACCOUNT",
                },
            },
        ]

        for test_case in test_cases:

            if test_case["description"] == "Default Values":
                result = self.run_function(
                    "construct_payable_receivable_mapping",
                    mock_vault,
                )
            else:
                result = self.run_function(
                    "construct_payable_receivable_mapping",
                    mock_vault,
                    test_case["payable_address"],
                    test_case["receivable_address"],
                    test_case["payable_internal_account"],
                    test_case["paid_internal_account"],
                    test_case["receivable_internal_account"],
                    test_case["received_internal_account"],
                )

            self.assertEqual(
                result.payable_address,
                test_case["expected_result"]["payable_address"],
            )
            self.assertEqual(
                result.receivable_address,
                test_case["expected_result"]["receivable_address"],
            )
            self.assertEqual(
                result.payable_internal_account,
                test_case["expected_result"]["payable_internal_account"],
            )
            self.assertEqual(
                result.paid_internal_account,
                test_case["expected_result"]["paid_internal_account"],
            )
            self.assertEqual(
                result.receivable_internal_account,
                test_case["expected_result"]["receivable_internal_account"],
            )
            self.assertEqual(
                result.received_internal_account,
                test_case["expected_result"]["received_internal_account"],
            )
            self.assertEqual(len(result.__annotations__.keys()), 6)

    def test_construct_accrual_details(self):
        mock_vault = self.create_mock()

        test_cases = [
            {
                "description": "Default Values",
                "expected_result": {
                    "instruction_description": None,
                    "base": "actual",
                    "precision": 5,
                    "rounding_mode": ROUND_HALF_UP,
                    "accrual_is_capitalised": False,
                    "net_postings": True,
                },
            },
            {
                "description": "No Default Values",
                "instruction_description": "test",
                "base": "360",
                "precision": 7,
                "rounding_mode": ROUND_FLOOR,
                "accrual_is_capitalised": True,
                "net_postings": False,
                "expected_result": {
                    "instruction_description": "test",
                    "base": "360",
                    "precision": 7,
                    "rounding_mode": ROUND_FLOOR,
                    "accrual_is_capitalised": True,
                    "net_postings": False,
                },
            },
        ]

        for test_case in test_cases:

            if test_case["description"] == "Default Values":
                result = self.run_function(
                    "construct_accrual_details",
                    mock_vault,
                    payable_receivable_mapping="SomeMappingNamedTuple",
                    denomination=DEFAULT_DENOMINATION,
                    balance=Decimal("10"),
                    rates={"tier_1": {"min": "0", "max": "100", "rate": "0.1"}},
                )
            else:
                result = self.run_function(
                    "construct_accrual_details",
                    mock_vault,
                    payable_receivable_mapping="SomeMappingNamedTuple",
                    denomination=DEFAULT_DENOMINATION,
                    balance=Decimal("10"),
                    rates={"tier_1": {"min": "0", "max": "100", "rate": "0.1"}},
                    instruction_description=test_case["instruction_description"],
                    base=test_case["base"],
                    precision=test_case["precision"],
                    rounding_mode=test_case["rounding_mode"],
                    accrual_is_capitalised=test_case["accrual_is_capitalised"],
                    net_postings=test_case["net_postings"],
                )

            self.assertEqual(result.payable_receivable_mapping, "SomeMappingNamedTuple")
            self.assertEqual(result.denomination, DEFAULT_DENOMINATION)
            self.assertEqual(result.balance, Decimal("10"))
            self.assertEqual(result.rates, {"tier_1": {"min": "0", "max": "100", "rate": "0.1"}})
            self.assertEqual(
                result.instruction_description,
                test_case["expected_result"]["instruction_description"],
            )
            self.assertEqual(result.base, test_case["expected_result"]["base"])
            self.assertEqual(result.precision, test_case["expected_result"]["precision"])
            self.assertEqual(result.rounding_mode, test_case["expected_result"]["rounding_mode"])
            self.assertEqual(
                result.accrual_is_capitalised,
                test_case["expected_result"]["accrual_is_capitalised"],
            )
            self.assertEqual(
                result.net_postings,
                test_case["expected_result"]["net_postings"],
            )

            self.assertEqual(len(result.__annotations__.keys()), 10)

    def test_construct_fee_details(self):
        mock_vault = self.create_mock()
        test_cases = [
            {
                "description": "Default Values",
                "expected_result": {
                    "instruction_description": None,
                },
            },
            {
                "description": "No Default Values",
                "instruction_description": "test",
                "expected_result": {
                    "instruction_description": "test",
                },
            },
        ]
        for test_case in test_cases:

            if test_case["description"] == "Default Values":
                result = self.run_function(
                    "construct_fee_details",
                    mock_vault,
                    payable_receivable_mapping="SomeMappingNamedTuple",
                    denomination=DEFAULT_DENOMINATION,
                    fee={"test_fee", Decimal("10")},
                )
            else:
                result = self.run_function(
                    "construct_fee_details",
                    mock_vault,
                    payable_receivable_mapping="SomeMappingNamedTuple",
                    denomination=DEFAULT_DENOMINATION,
                    fee={"test_fee", Decimal("10")},
                    instruction_description=test_case["instruction_description"],
                )

            self.assertEqual(result.payable_receivable_mapping, "SomeMappingNamedTuple")
            self.assertEqual(result.denomination, DEFAULT_DENOMINATION)
            self.assertEqual(result.fee, {"test_fee", Decimal("10")})
            self.assertEqual(
                result.instruction_description,
                test_case["expected_result"]["instruction_description"],
            )
            self.assertEqual(len(result.__annotations__.keys()), 4)

    def test_construct_charge_application_details(self):
        mock_vault = self.create_mock()
        test_cases = [
            {
                "description": "Default Values",
                "expected_result": {
                    "instruction_description": None,
                    "zero_out_description": None,
                    "precision": 2,
                    "rounding_mode": ROUND_HALF_UP,
                    "zero_out_remainder": False,
                    "apply_address": DEFAULT_ADDRESS,
                    "charge_type": "INTEREST",
                },
            },
            {
                "description": "No Default Values",
                "instruction_description": "test application",
                "zero_out_description": "test zero out",
                "precision": 5,
                "rounding_mode": ROUND_HALF_DOWN,
                "zero_out_remainder": True,
                "apply_address": "INTEREST_DUE",
                "charge_type": "FEES",
                "expected_result": {
                    "instruction_description": "test application",
                    "zero_out_description": "test zero out",
                    "precision": 5,
                    "rounding_mode": ROUND_HALF_DOWN,
                    "zero_out_remainder": True,
                    "apply_address": "INTEREST_DUE",
                    "charge_type": "FEES",
                },
            },
        ]
        for test_case in test_cases:

            if test_case["description"] == "Default Values":
                result = self.run_function(
                    "construct_charge_application_details",
                    mock_vault,
                    payable_receivable_mapping="SomeMappingNamedTuple",
                    denomination=DEFAULT_DENOMINATION,
                )
            else:
                result = self.run_function(
                    "construct_charge_application_details",
                    mock_vault,
                    payable_receivable_mapping="SomeMappingNamedTuple",
                    denomination=DEFAULT_DENOMINATION,
                    instruction_description=test_case["instruction_description"],
                    zero_out_description=test_case["zero_out_description"],
                    precision=test_case["precision"],
                    rounding_mode=test_case["rounding_mode"],
                    zero_out_remainder=test_case["zero_out_remainder"],
                    apply_address=test_case["apply_address"],
                    charge_type=test_case["charge_type"],
                )

            self.assertEqual(result.payable_receivable_mapping, "SomeMappingNamedTuple")
            self.assertEqual(result.denomination, DEFAULT_DENOMINATION)

            self.assertEqual(
                result.instruction_description,
                test_case["expected_result"]["instruction_description"],
            )
            self.assertEqual(
                result.zero_out_description,
                test_case["expected_result"]["zero_out_description"],
            )
            self.assertEqual(
                result.precision,
                test_case["expected_result"]["precision"],
            )
            self.assertEqual(
                result.rounding_mode,
                test_case["expected_result"]["rounding_mode"],
            )
            self.assertEqual(
                result.zero_out_remainder,
                test_case["expected_result"]["zero_out_remainder"],
            )
            self.assertEqual(
                result.apply_address,
                test_case["expected_result"]["apply_address"],
            )
            self.assertEqual(
                result.charge_type,
                test_case["expected_result"]["charge_type"],
            )
            self.assertEqual(len(result.__annotations__.keys()), 9)

    def test_charge_to_balance_dimensions(self):

        result = self.run_function(
            "_charge_to_balance_dimensions",
            vault_object=None,
            address=ACCRUED_DEPOSIT_PAYABLE,
            denomination=DEFAULT_DENOMINATION,
        )

        self.assertEqual(
            result,
            (
                ACCRUED_DEPOSIT + "_PAYABLE",
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                DEFAULT_PHASE,
            ),
        )

    def test_round_decimal(self):
        test_cases = [
            {
                "description": "5 dp round half up",
                "amount": Decimal("0.35184322311243"),
                "rounding": ROUND_HALF_UP,
                "decimal_places": 5,
                "expected_result": Decimal("0.35184"),
            },
            {
                "description": "1 dp round half up",
                "amount": Decimal("3.5184322311243"),
                "rounding": ROUND_HALF_UP,
                "decimal_places": 1,
                "expected_result": Decimal("3.5"),
            },
            {
                "description": "5 dp round floor",
                "amount": Decimal("0.3555455555"),
                "rounding": ROUND_FLOOR,
                "decimal_places": 5,
                "expected_result": Decimal("0.35554"),
            },
        ]
        for test_case in test_cases:

            result = self.run_function(
                "_round_decimal",
                vault_object=None,
                amount=test_case["amount"],
                decimal_places=test_case["decimal_places"],
                rounding=test_case["rounding"],
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_yearly_to_daily_rate(self):
        test_cases = [
            {
                "description": "leap year",
                "days_in_year": "actual",
                "yearly_rate": Decimal("0.035"),
                "year": 2020,
                "expected_result": Decimal("0.0000956284"),
            },
            {
                "description": "non-leap year",
                "days_in_year": "actual",
                "yearly_rate": Decimal("0.01375687438448813"),
                "year": 2019,
                "expected_result": Decimal("0.0000376901"),
            },
            {
                "description": "valid value, 360",
                "days_in_year": "360",
                "yearly_rate": Decimal("0.01375"),
                "year": 2020,
                "expected_result": Decimal("0.0000381944"),
            },
            {
                "description": "invalid value",
                "days_in_year": "340",
                "yearly_rate": "0.000273224043",
                "year": 2020,
                "expected_result": None,
            },
        ]

        for test_case in test_cases:

            result = self.run_function(
                "_yearly_to_daily_rate",
                vault_object=None,
                yearly_rate=test_case["yearly_rate"],
                year=test_case["year"],
                days_in_year=test_case["days_in_year"],
                rounding_mode=ROUND_HALF_UP,
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_is_leap_year(self):
        test_cases = [
            {
                "description": "2020 is a leap year",
                "year": 2020,
                "expected_result": True,
            },
            {
                "description": "2021 is not a leap year",
                "year": 2021,
                "expected_result": False,
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock()
            result = self.run_function(
                function_name="_is_leap_year",
                vault_object=mock_vault,
                year=test_case["year"],
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_calculate_accruals(self):
        test_cases = [
            {
                "description": "positive balance between min and max - single tier",
                "effective_balance": Decimal("400"),
                "rate_tiers": {"tier1": {"min": "100", "max": "1000", "rate": "0.01"}},
                "expected_accruals": [Decimal("0.00822")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 300.00.",
                ],
            },
            {
                "description": "positive balance, no min and max - single tier",
                "effective_balance": Decimal("1000"),
                "rate_tiers": {"tier1": {"rate": "0.01"}},
                "expected_accruals": [Decimal("0.02740")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 1000.00.",
                ],
            },
            {
                "description": "positive balance, no min and max - single tier, backdated 4 days",
                "effective_balance": Decimal("1000"),
                "rate_tiers": {"tier1": {"rate": "0.01"}},
                "number_of_days": "5",
                "expected_accruals": [Decimal("0.13700")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 1000.00.",
                ],
            },
            {
                "description": "zero balance, no min and max - single tier",
                "effective_balance": Decimal("0"),
                "rate_tiers": {"tier1": {"rate": "0.01"}},
                "expected_accruals": [],
                "expected_accrual_descriptions": [],
            },
            {
                "description": "positive balance at max - single tier",
                "effective_balance": Decimal("1000"),
                "rate_tiers": {"tier1": {"min": "100", "max": "1000", "rate": "0.01"}},
                "expected_accruals": [Decimal("0.02466")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 900.00.",
                ],
            },
            {
                "description": "positive balance exceeding max - single tier",
                "effective_balance": Decimal("1500"),
                "rate_tiers": {"tier1": {"min": "100", "max": "1000", "rate": "0.01"}},
                "expected_accruals": [Decimal("0.02466")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 900.00.",
                ],
            },
            {
                "description": "positive balance at min - single tier",
                "effective_balance": Decimal("100"),
                "rate_tiers": {"tier1": {"min": "100", "max": "1000", "rate": "0.01"}},
                "expected_accruals": [Decimal("0")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 0.00.",
                ],
            },
            {
                "description": "positive balance below min - single tier",
                "effective_balance": Decimal("50"),
                "rate_tiers": {"tier1": {"min": "100", "max": "1000", "rate": "0.01"}},
                "expected_accruals": [Decimal("0")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 0.00.",
                ],
            },
            {
                "description": "negative balance below min - single tier",
                "effective_balance": Decimal("-50"),
                "rate_tiers": {"tier1": {"min": "100", "max": "1000", "rate": "0.01"}},
                "expected_accruals": [Decimal("0")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 0.00.",
                ],
            },
            {
                "description": "positive balance min but no max - single tier",
                "effective_balance": Decimal("1500"),
                "rate_tiers": {"tier1": {"min": "100", "rate": "0.01"}},
                "expected_accruals": [Decimal("0.03836")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 1400.00.",
                ],
            },
            {
                "description": "negative balance min but no max - single tier",
                "effective_balance": Decimal("-1000"),
                "rate_tiers": {"tier1": {"min": "100", "rate": "0.01"}},
                "expected_accruals": [Decimal("0")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 0.00.",
                ],
            },
            {
                "description": "negative balance no min or max - single tier",
                "effective_balance": Decimal("-1000"),
                "rate_tiers": {"tier1": {"rate": "0.01"}},
                "expected_accruals": [Decimal("-0.02740")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of -1000.00.",
                ],
            },
            {
                "description": "negative balance between min and max - single tier",
                "effective_balance": Decimal("-400"),
                "rate_tiers": {"tier1": {"min": "-1000", "max": "-100", "rate": "0.01"}},
                "expected_accruals": [Decimal("-0.00822")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of -300.00.",
                ],
            },
            {
                "description": "negative balance at negative min - single tier",
                "effective_balance": Decimal("-1000"),
                "rate_tiers": {"tier1": {"min": "-1000", "max": "-100", "rate": "0.01"}},
                "expected_accruals": [Decimal("-0.02466")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of -900.00.",
                ],
            },
            {
                "description": "negative balance below negative min - single tier",
                "effective_balance": Decimal("-1500"),
                "rate_tiers": {"tier1": {"min": "-1000", "max": "-100", "rate": "0.01"}},
                "expected_accruals": [Decimal("-0.02466")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of -900.00.",
                ],
            },
            {
                "description": "negative balance above negative max - single tier",
                "effective_balance": Decimal("-50"),
                "rate_tiers": {"tier1": {"min": "-1000", "max": "-100", "rate": "0.01"}},
                "expected_accruals": [Decimal("0")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 0.00.",
                ],
            },
            {
                "description": "negative balance no min - single tier",
                "effective_balance": Decimal("-1500"),
                "rate_tiers": {"tier1": {"max": "-100", "rate": "0.01"}},
                "expected_accruals": [Decimal("-0.03836")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of -1400.00.",
                ],
            },
            {
                "description": "negative balance negative max, positive min - single tier",
                "effective_balance": Decimal("1500"),
                "rate_tiers": {"tier1": {"min": "1", "max": "-1", "rate": "0.01"}},
                "expected_accruals": [Decimal("0")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 0.00.",
                ],
            },
            {
                "description": "positive balance zero rate",
                "effective_balance": Decimal("1500"),
                "rate_tiers": {"tier1": {"rate": "0.00"}},
                "expected_accruals": [Decimal("0")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00000% on balance of 1500.00.",
                ],
            },
            {
                "description": "positive balance negative min, positive max - single tier",
                "effective_balance": Decimal("1500"),
                "rate_tiers": {"tier1": {"min": "-1", "max": "1", "rate": "0.01"}},
                "expected_accruals": [Decimal("0")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 0.00.",
                ],
            },
            {
                "description": "positive balance, positive min and max, min > max - single tier",
                "effective_balance": Decimal("1500"),
                "rate_tiers": {"tier1": {"min": "10", "max": "1", "rate": "0.01"}},
                "expected_accruals": [Decimal("0.0")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 0.00.",
                ],
            },
            {
                "description": "positive balance, negative min and max, min > max - single tier",
                "effective_balance": Decimal("1500"),
                "rate_tiers": {"tier1": {"min": "-1", "max": "-10", "rate": "0.01"}},
                "expected_accruals": [Decimal("0.0")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 0.00.",
                ],
            },
            {
                "description": "positive balance, zero min and max - single tier",
                "effective_balance": Decimal("1500"),
                "rate_tiers": {"tier1": {"min": "0", "max": "0", "rate": "0.01"}},
                "expected_accruals": [Decimal("0.0")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 0.00.",
                ],
            },
            {
                "description": "negative balance, negative min no max - single tier",
                "effective_balance": Decimal("-1500"),
                "rate_tiers": {"tier1": {"min": "-1000", "rate": "0.01"}},
                "expected_accruals": [Decimal("-0.02740")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of -1000.00.",
                ],
            },
            {
                "description": "positive balance, negative min no max - single tier",
                "effective_balance": Decimal("500"),
                "rate_tiers": {"tier1": {"min": "-1000", "max": "-100", "rate": "0.01"}},
                "expected_accruals": [Decimal("0")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 0.00.",
                ],
            },
            {
                "description": "positive balance, negative min and max - single tier",
                "effective_balance": Decimal("1000"),
                "rate_tiers": {"tier1": {"min": "-100", "rate": "0.01"}},
                "expected_accruals": [Decimal("0")],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00274% on balance of 0.00.",
                ],
            },
            {
                "description": "positive balance positive min and max for each tier - multi tier",
                "effective_balance": Decimal("1500"),
                "rate_tiers": {
                    "tier1": {"min": "10", "max": "100", "rate": "0.02"},
                    "tier2": {"min": "100", "max": "1000", "rate": "0.01"},
                    "tier3": {"min": "1000", "rate": "0.005"},
                },
                "expected_accruals": [
                    Decimal("0.00493"),
                    Decimal("0.02466"),
                    Decimal("0.00685"),
                ],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.00548% on balance of 90.00.",
                    "Daily interest accrued at 0.00274% on balance of 900.00.",
                    "Daily interest accrued at 0.00137% on balance of 500.00.",
                ],
            },
            {
                "description": "positive balance, positive tiers with mixed "
                "positive and negative rates - multi tier",
                "effective_balance": Decimal("1500"),
                "rate_tiers": {
                    "tier1": {"min": "10", "max": "100", "rate": "-0.02"},
                    "tier2": {"min": "100", "max": "1000", "rate": "0.01"},
                    "tier3": {"min": "1000", "rate": "-0.005"},
                },
                "expected_accruals": [
                    Decimal("-0.00493"),
                    Decimal("0.02466"),
                    Decimal("-0.00685"),
                ],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at -0.00548% on balance of 90.00.",
                    "Daily interest accrued at 0.00274% on balance of 900.00.",
                    "Daily interest accrued at -0.00137% on balance of 500.00.",
                ],
            },
            {
                "description": "positive balance > tier3 max, positive tiers with mixed "
                "positive and negative rates - multi tier",
                "effective_balance": Decimal("1500"),
                "rate_tiers": {
                    "tier1": {"min": "10", "max": "100", "rate": "-0.02"},
                    "tier2": {"min": "100", "max": "1000", "rate": "0.01"},
                    "tier3": {"min": "1000", "max": "1300", "rate": "-0.005"},
                },
                "expected_accruals": [
                    Decimal("-0.00493"),
                    Decimal("0.02466"),
                    Decimal("-0.00411"),
                ],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at -0.00548% on balance of 90.00.",
                    "Daily interest accrued at 0.00274% on balance of 900.00.",
                    "Daily interest accrued at -0.00137% on balance of 300.00.",
                ],
            },
            {
                "description": "balance at negative tier boundary",
                "effective_balance": Decimal("-5000"),
                "rate_tiers": {
                    "tier1": {"min": "-1500", "max": "-0", "rate": "0.09"},
                    "tier2": {"min": "-3000", "max": "-1500", "rate": "0.12"},
                    "tier3": {"min": "-5000", "max": "-3000", "rate": "0.15"},
                    "tier4": {"min": "-10000", "max": "-5000", "rate": "0.25"},
                },
                "expected_accruals": [
                    Decimal("-0.36986"),
                    Decimal("-0.49315"),
                    Decimal("-0.82192"),
                    # the zero accrual does not get converted to a posting
                    Decimal("-0"),
                ],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.02466% on balance of -1500.00.",
                    "Daily interest accrued at 0.03288% on balance of -1500.00.",
                    "Daily interest accrued at 0.04110% on balance of -2000.00.",
                    "Daily interest accrued at 0.06849% on balance of 0.00.",
                ],
            },
            {
                "description": "balance at positive tier boundary",
                "effective_balance": Decimal("5000"),
                "rate_tiers": {
                    "tier1": {"min": "0", "max": "1500", "rate": "0.09"},
                    "tier2": {"min": "1500", "max": "3000", "rate": "0.12"},
                    "tier3": {"min": "3000", "max": "5000", "rate": "0.15"},
                    "tier4": {"min": "5000", "max": "10000", "rate": "0.25"},
                },
                "expected_accruals": [
                    Decimal("0.36986"),
                    Decimal("0.49315"),
                    Decimal("0.82192"),
                    # the zero accrual does not get converted to a posting
                    Decimal("0"),
                ],
                "expected_accrual_descriptions": [
                    "Daily interest accrued at 0.02466% on balance of 1500.00.",
                    "Daily interest accrued at 0.03288% on balance of 1500.00.",
                    "Daily interest accrued at 0.04110% on balance of 2000.00.",
                    "Daily interest accrued at 0.06849% on balance of 0.00.",
                ],
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock()
            accrual_details = self.run_function(
                "construct_accrual_details",
                mock_vault,
                payable_receivable_mapping="SomeNamedTupleMapping",
                denomination=DEFAULT_DENOMINATION,
                balance=test_case["effective_balance"],
                rates=test_case["rate_tiers"],
                base="365",
                precision=5,
                rounding_mode=ROUND_HALF_UP,
            )

            accruals = self.run_function(
                "_calculate_accruals",
                None,
                accrual_details,
                effective_date=datetime(2019, 1, 1),
                number_of_days=int(test_case.get("number_of_days", 1)),
            )

            self.assertEqual(
                [accrual.amount for accrual in accruals],
                test_case["expected_accruals"],
                test_case["description"],
            )
            self.assertEqual(
                [accrual.description for accrual in accruals],
                test_case["expected_accrual_descriptions"],
                test_case["description"],
            )

    def test_create_accrual_postings_liability_net_positive_accrual(
        self,
    ):

        vault = self.create_mock()

        accruals = [
            PostingInfo(amount=Decimal("0.1"), description="tier_1"),
            PostingInfo(amount=Decimal("0.2"), description="tier_2"),
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        tside = "LIABILITY"
        net_postings = True

        expected_posting_calls = [
            call(
                amount=Decimal("0.3"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_PAYABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "_create_postings_for_accruals",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            accruals=accruals,
            instruction_description=instruction_description,
            tside=tside,
            net_postings=net_postings,
            event_type=ACCRUE_INTEREST,
            charge_type=DEFAULT_CHARGE_TYPE,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_accrual_postings_liability_no_net_positive_accrual(
        self,
    ):

        vault = self.create_mock()

        accruals = [
            PostingInfo(amount=Decimal("0.1"), description="tier_1"),
            PostingInfo(amount=Decimal("0.2"), description="tier_2"),
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        tside = "LIABILITY"
        net_postings = False

        expected_posting_calls = [
            call(
                amount=Decimal("0.1"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_PAYABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.2"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_PAYABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "_create_postings_for_accruals",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            accruals=accruals,
            instruction_description=instruction_description,
            tside=tside,
            net_postings=net_postings,
            event_type=ACCRUE_INTEREST,
            charge_type=DEFAULT_CHARGE_TYPE,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_accrual_postings_liability_net_negative_accrual(
        self,
    ):

        vault = self.create_mock()

        accruals = [
            PostingInfo(amount=Decimal("0.1"), description="tier_1"),
            PostingInfo(amount=Decimal("-0.2"), description="tier_2"),
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        tside = "LIABILITY"
        net_postings = True

        expected_posting_calls = [
            call(
                amount=Decimal("0.1"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                to_account_id="receivable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "_create_postings_for_accruals",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            accruals=accruals,
            instruction_description=instruction_description,
            tside=tside,
            net_postings=net_postings,
            event_type=ACCRUE_INTEREST,
            charge_type=DEFAULT_CHARGE_TYPE,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_accrual_postings_liability_no_net_negative_accrual(
        self,
    ):

        vault = self.create_mock()

        accruals = [
            PostingInfo(amount=Decimal("0.1"), description="tier_1"),
            PostingInfo(amount=Decimal("-0.2"), description="tier_2"),
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        tside = "LIABILITY"
        net_postings = False

        expected_posting_calls = [
            call(
                amount=Decimal("0.1"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_PAYABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.2"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                to_account_id="receivable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "_create_postings_for_accruals",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            accruals=accruals,
            instruction_description=instruction_description,
            tside=tside,
            net_postings=net_postings,
            event_type=ACCRUE_INTEREST,
            charge_type=DEFAULT_CHARGE_TYPE,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_accrual_postings_liability_zero_accrual(self):

        vault = self.create_mock()

        accruals = [
            PostingInfo(
                amount=Decimal("0"),
            ),
            PostingInfo(
                amount=Decimal("0"),
            ),
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        tside = "LIABILITY"
        net_postings = True

        self.run_function(
            "_create_postings_for_accruals",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            accruals=accruals,
            instruction_description=instruction_description,
            tside=tside,
            net_postings=net_postings,
            event_type=ACCRUE_INTEREST,
            charge_type=DEFAULT_CHARGE_TYPE,
        )

        vault.make_internal_transfer_instructions.assert_not_called()

    def test_create_accrual_postings_asset_net_positive_accrual(
        self,
    ):

        vault = self.create_mock()

        accruals = [
            PostingInfo(amount=Decimal("0.1"), description="tier_1"),
            PostingInfo(amount=Decimal("0.2"), description="tier_2"),
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_INTEREST_PAYABLE,
            ACCRUED_INTEREST_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        tside = "ASSET"
        net_postings = True

        expected_posting_calls = [
            call(
                amount=Decimal("0.3"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_INTEREST_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_INTEREST_RECEIVABLE",
                to_account_id="receivable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "_create_postings_for_accruals",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            accruals=accruals,
            instruction_description=instruction_description,
            tside=tside,
            net_postings=net_postings,
            event_type=ACCRUE_INTEREST,
            charge_type=DEFAULT_CHARGE_TYPE,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_accrual_postings_asset_no_net_positive_accrual(
        self,
    ):

        vault = self.create_mock()

        accruals = [
            PostingInfo(amount=Decimal("0.1"), description="tier_1"),
            PostingInfo(amount=Decimal("0.2"), description="tier_2"),
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_INTEREST_PAYABLE,
            ACCRUED_INTEREST_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        tside = "ASSET"
        net_postings = False

        expected_posting_calls = [
            call(
                amount=Decimal("0.1"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_INTEREST_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_INTEREST_RECEIVABLE",
                to_account_id="receivable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.2"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_INTEREST_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_INTEREST_RECEIVABLE",
                to_account_id="receivable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "_create_postings_for_accruals",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            accruals=accruals,
            instruction_description=instruction_description,
            tside=tside,
            net_postings=net_postings,
            event_type=ACCRUE_INTEREST,
            charge_type=DEFAULT_CHARGE_TYPE,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_accrual_postings_asset_net_negative_accrual(
        self,
    ):

        vault = self.create_mock()

        accruals = [
            PostingInfo(amount=Decimal("0.1"), description="tier_1"),
            PostingInfo(amount=Decimal("-0.2"), description="tier_2"),
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_INTEREST_PAYABLE,
            ACCRUED_INTEREST_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        tside = "ASSET"
        net_postings = True

        expected_posting_calls = [
            call(
                amount=Decimal("0.1"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_INTEREST_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_INTEREST_PAYABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "_create_postings_for_accruals",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            accruals=accruals,
            instruction_description=instruction_description,
            tside=tside,
            net_postings=net_postings,
            event_type=ACCRUE_INTEREST,
            charge_type=DEFAULT_CHARGE_TYPE,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_accrual_postings_asset_no_net_negative_accrual(
        self,
    ):

        vault = self.create_mock()

        accruals = [
            PostingInfo(amount=Decimal("0.1"), description="tier_1"),
            PostingInfo(amount=Decimal("-0.2"), description="tier_2"),
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_INTEREST_PAYABLE,
            ACCRUED_INTEREST_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        tside = "ASSET"
        net_postings = False

        expected_posting_calls = [
            call(
                amount=Decimal("0.1"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_INTEREST_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_INTEREST_RECEIVABLE",
                to_account_id="receivable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.2"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_INTEREST_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_INTEREST_PAYABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "_create_postings_for_accruals",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            accruals=accruals,
            instruction_description=instruction_description,
            tside=tside,
            net_postings=net_postings,
            event_type=ACCRUE_INTEREST,
            charge_type=DEFAULT_CHARGE_TYPE,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_accrual_postings_asset_zero_accrual(self):

        vault = self.create_mock()

        accruals = [
            PostingInfo(amount=Decimal("0"), description="tier_1"),
            PostingInfo(amount=Decimal("0"), description="tier_2"),
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_INTEREST_PAYABLE,
            ACCRUED_INTEREST_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        tside = "ASSET"
        net_postings = True

        self.run_function(
            "_create_postings_for_accruals",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            accruals=accruals,
            instruction_description=instruction_description,
            tside=tside,
            net_postings=net_postings,
            event_type=ACCRUE_INTEREST,
            charge_type=DEFAULT_CHARGE_TYPE,
        )

        vault.make_internal_transfer_instructions.assert_not_called()

    def test_calculate_application_round_up(self):

        balances = [Balance(net=Decimal("0.13661"))]

        expected_applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.14"),
                    description="Accrued interest applied.",
                ),
                "remainder": PostingInfo(
                    amount=Decimal("-0.00339"),
                    description="Zero out remainder after accrued interest applied.",
                ),
            }
        ]

        applications = self.run_function(
            "_calculate_application_and_remainders",
            None,
            balances,
            precision=2,
            rounding_mode=ROUND_HALF_UP,
            charge_type="INTEREST",
        )

        self.assertEqual(len(applications), len(expected_applications))
        for i, expected_app in enumerate(expected_applications):
            for k, expected_posting_info in expected_app.items():
                self.assertTrue(
                    posting_info_equal(
                        applications[i][k],
                        expected_posting_info,
                    )
                )

    def test_calculate_application_round_down(self):

        balances = [Balance(net=Decimal("0.27322"))]

        expected_applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.27"),
                    description="Accrued interest applied.",
                ),
                "remainder": PostingInfo(
                    amount=Decimal("0.00322"),
                    description="Zero out remainder after accrued interest applied.",
                ),
            }
        ]

        applications = self.run_function(
            "_calculate_application_and_remainders",
            None,
            balances,
            precision=2,
            rounding_mode=ROUND_HALF_UP,
            charge_type="INTEREST",
        )

        self.assertEqual(len(applications), len(expected_applications))
        for i, expected_app in enumerate(expected_applications):
            for k, expected_posting_info in expected_app.items():
                self.assertTrue(
                    posting_info_equal(
                        applications[i][k],
                        expected_posting_info,
                    )
                )

    def test_calculate_application_non_default_precision(self):

        balances = [Balance(net=Decimal("0.13661"))]

        expected_applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.1366"),
                    description="Accrued interest applied.",
                ),
                "remainder": PostingInfo(
                    amount=Decimal("0.00001"),
                    description="Zero out remainder after accrued interest applied.",
                ),
            }
        ]

        applications = self.run_function(
            "_calculate_application_and_remainders",
            None,
            balances,
            precision=4,
            rounding_mode=ROUND_HALF_UP,
            charge_type="INTEREST",
        )

        self.assertEqual(len(applications), len(expected_applications))
        for i, expected_app in enumerate(expected_applications):
            for k, expected_posting_info in expected_app.items():
                self.assertTrue(
                    posting_info_equal(
                        applications[i][k],
                        expected_posting_info,
                    )
                )

    def test_calculate_application_non_default_rounding_mode(self):

        balances = [Balance(net=Decimal("0.131"))]

        expected_applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.14"),
                    description="Accrued interest applied.",
                ),
                "remainder": PostingInfo(
                    amount=Decimal("-0.009"),
                    description="Zero out remainder after accrued interest applied.",
                ),
            }
        ]

        applications = self.run_function(
            "_calculate_application_and_remainders",
            None,
            balances,
            rounding_mode=ROUND_CEILING,
            precision=2,
            charge_type="INTEREST",
        )

        self.assertEqual(len(applications), len(expected_applications))
        for i, expected_app in enumerate(expected_applications):
            for k, expected_posting_info in expected_app.items():
                self.assertTrue(
                    posting_info_equal(
                        applications[i][k],
                        expected_posting_info,
                    )
                )

    def test_calculate_application_negative_round_up(self):

        balances = [Balance(net=Decimal("-0.13661"))]

        expected_applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("-0.14"),
                    description="Accrued interest applied.",
                ),
                "remainder": PostingInfo(
                    amount=Decimal("0.00339"),
                    description="Zero out remainder after accrued interest applied.",
                ),
            }
        ]

        applications = self.run_function(
            "_calculate_application_and_remainders",
            None,
            balances,
            precision=2,
            rounding_mode=ROUND_HALF_UP,
            charge_type="INTEREST",
        )

        self.assertEqual(len(applications), len(expected_applications))
        for i, expected_app in enumerate(expected_applications):
            for k, expected_posting_info in expected_app.items():
                self.assertTrue(
                    posting_info_equal(
                        applications[i][k],
                        expected_posting_info,
                    )
                )

    def test_calculate_application_negative_round_down(self):

        balances = [Balance(net=Decimal("-0.27322"))]
        expected_applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("-0.27"),
                    description="Accrued interest applied.",
                ),
                "remainder": PostingInfo(
                    amount=Decimal("-0.00322"),
                    description="Zero out remainder after accrued interest applied.",
                ),
            }
        ]

        applications = self.run_function(
            "_calculate_application_and_remainders",
            None,
            balances,
            precision=2,
            rounding_mode=ROUND_HALF_UP,
            charge_type="INTEREST",
        )

        self.assertEqual(len(applications), len(expected_applications))
        for i, expected_app in enumerate(expected_applications):
            for k, expected_posting_info in expected_app.items():
                self.assertTrue(
                    posting_info_equal(
                        applications[i][k],
                        expected_posting_info,
                    )
                )

    def test_create_application_postings_liability_payable_no_zeroing_out(self):

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.14"),
                    description="Accrued interest applied.",
                ),
                "remainder": PostingInfo(
                    amount=Decimal("-0.00339"),
                    description="Zero out remainder after accrued interest applied.",
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "LIABILITY"
        zero_out_remainder = False
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="paid_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_liability_payable_zero_out_negative_remainder(
        self,
    ):

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.14"),
                ),
                "remainder": PostingInfo(
                    amount=Decimal("-0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test application"
        zero_out_description = "test zero out"
        account_tside = "LIABILITY"
        zero_out_remainder = True
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="paid_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test application",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test application",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            # These are the same as a payable interest accrual
            call(
                amount=Decimal("0.00339"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_PAYABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test zero out",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            zero_out_description=zero_out_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_liability_payable_zero_out_positive_remainder(
        self,
    ):

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.14"),
                ),
                "remainder": PostingInfo(
                    Decimal("0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "LIABILITY"
        zero_out_remainder = True
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="paid_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            # reverse = True
            call(
                amount=Decimal("0.00339"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"REVERSE_ACCRUED_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            zero_out_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_liability_receivable_no_zeroing_out(self):

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("-0.14"),
                ),
                "remainder": PostingInfo(
                    amount=Decimal("-0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "LIABILITY"
        zero_out_remainder = False
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="received_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_liability_receivable_zero_out_negative_remainder(
        self,
    ):

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("-0.14"),
                ),
                "remainder": PostingInfo(
                    amount=Decimal("-0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "LIABILITY"
        zero_out_remainder = True
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="received_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            # reverse = True
            call(
                amount=Decimal("0.00339"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"REVERSE_ACCRUED_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            zero_out_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_liability_receivable_zero_out_positive_remainder(
        self,
    ):

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("-0.14"),
                ),
                "remainder": PostingInfo(
                    amount=Decimal("0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "LIABILITY"
        zero_out_remainder = True
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="received_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            # These are the same as a receivable interest accrual
            call(
                amount=Decimal("0.00339"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                to_account_id="receivable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            zero_out_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_liability_zero_application_positive_remainder(
        self,
    ):
        """
        This tests when interest is applied on a liability account where we apply interest on
        a payable address (i.e ACCRUED_DEPOSIT_PAYABLE) with a balance of 0.00339
        therefore application = 0
        we still expect the zero out postings to be made to reverse the accrued interest
        """

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.00"),
                ),
                "remainder": PostingInfo(
                    amount=Decimal("0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "LIABILITY"
        zero_out_remainder = True
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.00339"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"REVERSE_ACCRUED_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            zero_out_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_liability_zero_application_negative_remainder(
        self,
    ):
        """
        This tests when interest is applied on a liability account where we apply interest on
        a receivable address (i.e ACCRUED_DEPOSIT_RECEIVABLE) with a balance of -0.00339
        therefore application = 0
        we still expect the zero out postings to be made to reverse the accrued interest
        """

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.00"),
                ),
                "remainder": PostingInfo(
                    amount=Decimal("-0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "LIABILITY"
        zero_out_remainder = True
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.00339"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"REVERSE_ACCRUED_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            zero_out_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_asset_payable_no_zeroing_out(self):

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("-0.14"),
                ),
                "remainder": PostingInfo(
                    amount=Decimal("-0.00339"),
                ),
            }
        ]

        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "ASSET"
        zero_out_remainder = False
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="paid_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_asset_payable_zero_out_negative_remainder(
        self,
    ):

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("-0.14"),
                ),
                "remainder": PostingInfo(
                    amount=Decimal("-0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "ASSET"
        zero_out_remainder = True
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="paid_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            # reverse = True
            call(
                amount=Decimal("0.00339"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"REVERSE_ACCRUED_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            zero_out_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_asset_payable_zero_out_positive_remainder(
        self,
    ):

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("-0.14"),
                ),
                "remainder": PostingInfo(
                    Decimal("0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "ASSET"
        zero_out_remainder = True
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="paid_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            # These are the same as a payable interest accrual
            call(
                amount=Decimal("0.00339"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_PAYABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            zero_out_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_asset_receivable_no_zeroing_out(self):

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.14"),
                ),
                "remainder": PostingInfo(
                    amount=Decimal("-0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "ASSET"
        zero_out_remainder = False
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="received_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_asset_receivable_zero_out_negative_remainder(
        self,
    ):

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.14"),
                ),
                "remainder": PostingInfo(
                    amount=Decimal("-0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "ASSET"
        zero_out_remainder = True
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="received_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            # These are the same as a receivable interest accrual
            call(
                amount=Decimal("0.00339"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                to_account_id="receivable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            zero_out_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_asset_receivable_zero_out_positive_remainder(
        self,
    ):

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.14"),
                ),
                "remainder": PostingInfo(
                    Decimal("0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "ASSET"
        zero_out_remainder = True
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="received_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            # reverse = True
            call(
                amount=Decimal("0.00339"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"REVERSE_ACCRUED_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            zero_out_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_asset_zero_application_negative_remainder(
        self,
    ):
        """
        This tests when interest is applied on an asset account where we apply interest on
        a payable address (i.e ACCRUED_DEPOSIT_PAYABLE) with a balance of -0.00339
        therefore application = 0
        we still expect the zero out postings to be made to reverse the accrued interest
        """

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.00"),
                ),
                "remainder": PostingInfo(
                    amount=Decimal("-0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "ASSET"
        zero_out_remainder = True
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.00339"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"REVERSE_ACCRUED_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            zero_out_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_application_postings_asset_zero_application_positive_remainder(
        self,
    ):
        """
        This tests when interest is applied on an asset account where we apply interest on
        a receivable address (i.e ACCRUED_DEPOSIT_RECEIVABLE) with a balance of 0.00339
        therefore application = 0
        we still expect the zero out postings to be made to reverse the accrued interest
        """

        vault = self.create_mock()

        applications = [
            {
                "application": PostingInfo(
                    amount=Decimal("0.00"),
                ),
                "remainder": PostingInfo(
                    Decimal("0.00339"),
                ),
            }
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            "CAPITALISED_INTEREST_PAYABLE",
            "CAPITALISED_INTEREST_RECEIVABLE",
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "ASSET"
        zero_out_remainder = True
        apply_address = DEFAULT_ADDRESS

        expected_posting_calls = [
            call(
                amount=Decimal("0.00339"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"REVERSE_ACCRUED_INTEREST_{HOOK_EXECUTION_ID}"
                f"_CAPITALISED_INTEREST_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="CAPITALISED_INTEREST_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": APPLY_ACCRUED_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_postings_for_applications",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            applications=applications,
            instruction_description=instruction_description,
            zero_out_description=instruction_description,
            account_tside=account_tside,
            zero_out_remainder=zero_out_remainder,
            apply_address=apply_address,
            event_type=APPLY_ACCRUED_INTEREST,
            charge_type="INTEREST",
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_capitalised_accrual_postings_asset_payable(self):

        vault = self.create_mock()

        accruals = [
            PostingInfo(
                amount=Decimal("-0.14"),
            )
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            "CAPITALISED_INTEREST_PAYABLE",
            "CAPITALISED_INTEREST_RECEIVABLE",
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "ASSET"

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"_ACCRUE_AND_CAPITALISE_INTEREST"
                f"_{HOOK_EXECUTION_ID}_CAPITALISED_INTEREST_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="CAPITALISED_INTEREST_PAYABLE",
                to_account_id="paid_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "False",
                    "account_type": "",
                },
                override_all_restrictions=True,
            )
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_capitalised_accrual_postings",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            accruals=accruals,
            denomination=DEFAULT_DENOMINATION,
            account_tside=account_tside,
            instruction_description=instruction_description,
            event_type=ACCRUE_INTEREST,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_capitalised_accrual_postings_multiple_accruals(self):

        vault = self.create_mock()

        accruals = [
            PostingInfo(
                amount=Decimal("-0.14"),
            ),
            PostingInfo(
                amount=Decimal("-0.14"),
            ),
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            "CAPITALISED_INTEREST_PAYABLE",
            "CAPITALISED_INTEREST_RECEIVABLE",
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "ASSET"

        expected_posting_calls = [
            call(
                amount=Decimal("0.28"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"_ACCRUE_AND_CAPITALISE_INTEREST"
                f"_{HOOK_EXECUTION_ID}_CAPITALISED_INTEREST_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="CAPITALISED_INTEREST_PAYABLE",
                to_account_id="paid_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "False",
                    "account_type": "",
                },
                override_all_restrictions=True,
            )
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_capitalised_accrual_postings",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            accruals=accruals,
            denomination=DEFAULT_DENOMINATION,
            account_tside=account_tside,
            instruction_description=instruction_description,
            event_type=ACCRUE_INTEREST,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_capitalised_accrual_postings_asset_receivable(self):

        vault = self.create_mock()

        accruals = [
            PostingInfo(
                amount=Decimal("0.14"),
            )
        ]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            "CAPITALISED_INTEREST_PAYABLE",
            "CAPITALISED_INTEREST_RECEIVABLE",
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "ASSET"

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"_ACCRUE_AND_CAPITALISE_INTEREST"
                f"_{HOOK_EXECUTION_ID}_CAPITALISED_INTEREST_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="received_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="CAPITALISED_INTEREST_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "False",
                    "account_type": "",
                },
                override_all_restrictions=True,
            )
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_capitalised_accrual_postings",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            accruals=accruals,
            denomination=DEFAULT_DENOMINATION,
            account_tside=account_tside,
            instruction_description=instruction_description,
            event_type=ACCRUE_INTEREST,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_capitalised_accrual_postings_liability_payable(self):

        vault = self.create_mock()

        accruals = [PostingInfo(amount=Decimal("0.14"))]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "LIABILITY"

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"_ACCRUE_AND_CAPITALISE_INTEREST"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="paid_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "False",
                    "account_type": "",
                },
                override_all_restrictions=True,
            )
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_capitalised_accrual_postings",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            accruals=accruals,
            denomination=DEFAULT_DENOMINATION,
            account_tside=account_tside,
            instruction_description=instruction_description,
            event_type=ACCRUE_INTEREST,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_create_capitalised_accrual_postings_liability_receivable(self):

        vault = self.create_mock()

        accruals = [PostingInfo(amount=Decimal("-0.14"))]
        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        instruction_description = "test"
        account_tside = "LIABILITY"

        expected_posting_calls = [
            call(
                amount=Decimal("0.14"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"_ACCRUE_AND_CAPITALISE_INTEREST"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="received_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "False",
                    "account_type": "",
                },
                override_all_restrictions=True,
            )
        ]

        vault = self.create_mock()

        self.run_function(
            "_create_capitalised_accrual_postings",
            vault,
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            accruals=accruals,
            denomination=DEFAULT_DENOMINATION,
            account_tside=account_tside,
            instruction_description=instruction_description,
            event_type=ACCRUE_INTEREST,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_reverse_interest_liability(self):

        balance_ts = balances_for_current_account(
            accrued_deposit_payable=Decimal("10.47581"),
            accrued_deposit_receivable=Decimal("-1.44445"),
            default_balance=Decimal("1000"),
        )
        vault = self.create_mock(balance_ts=balance_ts)

        balances = {
            (
                ACCRUED_DEPOSIT_PAYABLE,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=Decimal("10.47581")),
            (
                ACCRUED_DEPOSIT_RECEIVABLE,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=-Decimal("1.44445")),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=Decimal("1000")),
        }

        account_tside = "LIABILITY"

        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )

        accrual_details = self.run_function(
            "construct_accrual_details",
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            balance=0,
            rates={},
            base="365",
            precision=5,
            rounding_mode=ROUND_HALF_UP,
            accrual_is_capitalised=False,
        )

        expected_posting_calls = [
            call(
                amount=Decimal("10.47581"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"REVERSE_ACCRUED_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Reversing accrued interest",
                    "event": CLOSE_ACCOUNT,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("1.44445"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"REVERSE_ACCRUED_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Reversing accrued interest",
                    "event": CLOSE_ACCOUNT,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "reverse_interest",
            vault,
            vault,
            balances=balances,
            interest_dimensions=[accrual_details],
            account_tside=account_tside,
            event_type=CLOSE_ACCOUNT,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_reverse_interest_asset(self):

        balance_ts = balances_for_current_account(
            accrued_deposit_payable=Decimal("-10.47581"),
            accrued_deposit_receivable=Decimal("1.44445"),
            default_balance=Decimal("1000"),
        )
        vault = self.create_mock(balance_ts=balance_ts)

        balances = {
            (
                ACCRUED_DEPOSIT_PAYABLE,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=Decimal("-10.47581")),
            (
                ACCRUED_DEPOSIT_RECEIVABLE,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=Decimal("1.44445")),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=Decimal("1000")),
        }

        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )

        account_tside = "ASSET"

        accrual_details = self.run_function(
            "construct_accrual_details",
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            balance=0,
            rates={},
            instruction_description="Reverse ACCRUED_DEPOSIT interest due to account closure",
            base="365",
            precision=5,
            rounding_mode=ROUND_HALF_UP,
            accrual_is_capitalised=False,
        )

        expected_posting_calls = [
            call(
                amount=Decimal("10.47581"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"REVERSE_ACCRUED_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Reverse ACCRUED_DEPOSIT interest due to account closure",
                    "event": "CLOSE_ACCOUNT",
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("1.44445"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"REVERSE_ACCRUED_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Reverse ACCRUED_DEPOSIT interest due to account closure",
                    "event": "CLOSE_ACCOUNT",
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "reverse_interest",
            vault,
            vault,
            balances=balances,
            interest_dimensions=[accrual_details],
            account_tside=account_tside,
            event_type=CLOSE_ACCOUNT,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_apply_charges_fees(self):

        balance_ts = balances_for_current_account(
            accrued_deposit_payable=Decimal("10.47581"),
            accrued_deposit_receivable=Decimal("-1.44445"),
            accrued_overdraft=Decimal("-150"),
            default_balance=Decimal("1000"),
        )
        vault = self.create_mock(balance_ts=balance_ts)

        balances = {
            (
                ACCRUED_OVERDRAFT_RECEIVABLE,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=Decimal("-150")),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=Decimal("1000")),
        }

        payable_receivable_mapping_deposit = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )

        payable_receivable_mapping_overdraft = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_OVERDRAFT_PAYABLE,
            ACCRUED_OVERDRAFT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )

        account_tside = "LIABILITY"
        charge_details_deposit = self.run_function(
            "construct_charge_application_details",
            vault,
            payable_receivable_mapping=payable_receivable_mapping_deposit,
            denomination=DEFAULT_DENOMINATION,
            precision=2,
            rounding_mode=ROUND_HALF_UP,
            zero_out_remainder=False,
            apply_address=DEFAULT_ADDRESS,
            charge_type="FEES",
        )

        charge_details_overdraft = self.run_function(
            "construct_charge_application_details",
            vault,
            payable_receivable_mapping=payable_receivable_mapping_overdraft,
            denomination=DEFAULT_DENOMINATION,
            precision=2,
            rounding_mode=ROUND_HALF_UP,
            zero_out_remainder=False,
            apply_address=DEFAULT_ADDRESS,
            charge_type="FEES",
        )

        expected_posting_calls = [
            call(
                amount=Decimal("150.00"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_FEES_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="received_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Accrued fees applied.",
                    "event": APPLY_CHARGES,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("150.00"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_FEES_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address=ACCRUED_OVERDRAFT_RECEIVABLE,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Accrued fees applied.",
                    "event": APPLY_CHARGES,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "apply_charges",
            vault,
            vault,
            balances=balances,
            charge_details=[charge_details_deposit, charge_details_overdraft],
            account_tside=account_tside,
            event_type=APPLY_CHARGES,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_apply_charges_interest(self):

        balance_ts = balances_for_current_account(
            accrued_deposit_payable=Decimal("10.47581"),
            accrued_deposit_receivable=Decimal("-1.44445"),
            accrued_overdraft=Decimal("-150"),
            default_balance=Decimal("1000"),
        )
        vault = self.create_mock(balance_ts=balance_ts)

        balances = {
            (
                ACCRUED_DEPOSIT_PAYABLE,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=Decimal("10.47581")),
            (
                ACCRUED_DEPOSIT_RECEIVABLE,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=Decimal("-1.44445")),
            (
                ACCRUED_OVERDRAFT_RECEIVABLE,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=Decimal("-150")),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=Decimal("1000")),
        }

        payable_receivable_mapping_deposit = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )

        payable_receivable_mapping_overdraft = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_OVERDRAFT_PAYABLE,
            ACCRUED_OVERDRAFT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )

        account_tside = "LIABILITY"
        charge_details_deposit = self.run_function(
            "construct_charge_application_details",
            vault,
            payable_receivable_mapping=payable_receivable_mapping_deposit,
            denomination=DEFAULT_DENOMINATION,
            precision=2,
            rounding_mode=ROUND_HALF_UP,
            zero_out_remainder=False,
            apply_address=DEFAULT_ADDRESS,
        )

        charge_details_overdraft = self.run_function(
            "construct_charge_application_details",
            vault,
            payable_receivable_mapping=payable_receivable_mapping_overdraft,
            denomination=DEFAULT_DENOMINATION,
            precision=2,
            rounding_mode=ROUND_HALF_UP,
            zero_out_remainder=False,
            apply_address=DEFAULT_ADDRESS,
        )

        expected_posting_calls = [
            call(
                amount=Decimal("10.48"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="paid_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Accrued interest applied.",
                    "event": APPLY_CHARGES,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("10.48"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address=ACCRUED_DEPOSIT_PAYABLE,
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Accrued interest applied.",
                    "event": APPLY_CHARGES,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("1.44"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="received_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Accrued interest applied.",
                    "event": APPLY_CHARGES,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("1.44"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address=ACCRUED_DEPOSIT_RECEIVABLE,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Accrued interest applied.",
                    "event": APPLY_CHARGES,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("150.00"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="received_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Accrued interest applied.",
                    "event": APPLY_CHARGES,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("150.00"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="receivable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_OVERDRAFT_RECEIVABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Accrued interest applied.",
                    "event": APPLY_CHARGES,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "apply_charges",
            vault,
            vault,
            balances=balances,
            charge_details=[charge_details_deposit, charge_details_overdraft],
            account_tside=account_tside,
            event_type=APPLY_CHARGES,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_apply_charges_custom_instruction_descriptions(self):

        balance_ts = balances_for_current_account(
            accrued_deposit_payable=Decimal("10.47581"),
            default_balance=Decimal("1000"),
        )
        vault = self.create_mock(balance_ts=balance_ts)

        balances = {
            (
                ACCRUED_DEPOSIT_PAYABLE,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=Decimal("10.47581")),
            (
                DEFAULT_ADDRESS,
                DEFAULT_ASSET,
                DEFAULT_DENOMINATION,
                Phase.COMMITTED,
            ): Balance(net=Decimal("1000")),
        }

        payable_receivable_mapping_deposit = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )

        payable_receivable_mapping_overdraft = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_OVERDRAFT_PAYABLE,
            ACCRUED_OVERDRAFT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )
        custom_application_description = "Applied accrued interest."
        custom_zero_out_description = "Zeroing out after interest accrued."
        account_tside = "LIABILITY"
        charge_details_deposit = self.run_function(
            "construct_charge_application_details",
            vault,
            payable_receivable_mapping=payable_receivable_mapping_deposit,
            denomination=DEFAULT_DENOMINATION,
            precision=2,
            rounding_mode=ROUND_HALF_UP,
            zero_out_remainder=True,
            apply_address=DEFAULT_ADDRESS,
            instruction_description=custom_application_description,
            zero_out_description=custom_zero_out_description,
        )

        charge_details_overdraft = self.run_function(
            "construct_charge_application_details",
            vault,
            payable_receivable_mapping=payable_receivable_mapping_overdraft,
            denomination=DEFAULT_DENOMINATION,
            precision=2,
            rounding_mode=ROUND_HALF_UP,
            zero_out_remainder=True,
            apply_address=DEFAULT_ADDRESS,
            instruction_description=custom_application_description,
            zero_out_description=custom_zero_out_description,
        )

        expected_posting_calls = [
            call(
                amount=Decimal("10.48"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_PRIMARY_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="paid_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": custom_application_description,
                    "event": APPLY_CHARGES,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("10.48"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"APPLY_INTEREST_OFFSET_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_PAYABLE",
                to_account_id="payable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": custom_application_description,
                    "event": APPLY_CHARGES,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.00419"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                asset=DEFAULT_ASSET,
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_PAYABLE",
                instruction_details={
                    "description": custom_zero_out_description,
                    "event": APPLY_CHARGES,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "apply_charges",
            vault,
            vault,
            balances=balances,
            charge_details=[charge_details_deposit, charge_details_overdraft],
            account_tside=account_tside,
            event_type=APPLY_CHARGES,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_accrue_interest(self):
        vault = self.create_mock()

        payable_receivable_mapping_deposit = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )

        payable_receivable_mapping_deposit_overdraft_fee = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_OVERDRAFT_FEE_PAYABLE,
            ACCRUED_OVERDRAFT_FEE_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )

        account_tside = "LIABILITY"

        accrual_details = self.run_function(
            "construct_accrual_details",
            vault,
            payable_receivable_mapping=payable_receivable_mapping_deposit,
            denomination=DEFAULT_DENOMINATION,
            balance=Decimal("1000"),
            rates={"tier_1": {"rate": Decimal("0.1")}},
            base="365",
            precision=5,
            rounding_mode=ROUND_HALF_UP,
            accrual_is_capitalised=False,
        )

        accrual_details_capitalised = self.run_function(
            "construct_accrual_details",
            vault,
            payable_receivable_mapping=payable_receivable_mapping_deposit_overdraft_fee,
            denomination=DEFAULT_DENOMINATION,
            balance=Decimal("1000"),
            rates={"tier_1": {"rate": Decimal("0.2")}},
            base="365",
            precision=2,
            rounding_mode=ROUND_HALF_UP,
            accrual_is_capitalised=True,
        )

        expected_posting_calls = [
            call(
                amount=Decimal("0.27397"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_PAYABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Daily interest accrued at 0.02740% on balance of 1000.00.",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.55"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"_ACCRUE_AND_CAPITALISE_INTEREST"
                f"_{HOOK_EXECUTION_ID}_ACCRUED_OVERDRAFT_FEE_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_OVERDRAFT_FEE_PAYABLE",
                to_account_id="paid_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Daily interest accrued at 0.05479% on balance of 1000.00.",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "False",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "accrue_interest",
            vault,
            vault,
            accrual_details=[accrual_details, accrual_details_capitalised],
            account_tside=account_tside,
            effective_date=datetime(2019, 1, 1),
            event_type=ACCRUE_INTEREST,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_accrue_interest_net_postings_across_tiers(self):
        vault = self.create_mock()

        payable_receivable_mapping_deposit = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )

        account_tside = "LIABILITY"

        accrual_details = self.run_function(
            "construct_accrual_details",
            vault,
            payable_receivable_mapping=payable_receivable_mapping_deposit,
            denomination=DEFAULT_DENOMINATION,
            balance=Decimal("3000"),
            rates={
                "tier_1": {
                    "min": Decimal("0"),
                    "max": Decimal("1000"),
                    "rate": Decimal("0.2"),
                },
                "tier_2": {
                    "min": Decimal("1000"),
                    "max": Decimal("2000"),
                    "rate": Decimal("0.1"),
                },
                "tier_3": {
                    "min": Decimal("2000"),
                    "max": Decimal("3000"),
                    "rate": Decimal("-0.1"),
                },
            },
            base="365",
            precision=5,
            rounding_mode=ROUND_HALF_UP,
            accrual_is_capitalised=False,
            net_postings=True,
        )

        expected_posting_calls = [
            call(
                amount=Decimal("0.54795"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_PAYABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Aggregate of: "
                    + "Daily interest accrued at 0.05479% on balance of 1000.00. "
                    + "Daily interest accrued at 0.02740% on balance of 1000.00. "
                    + "Daily interest accrued at -0.02740% on balance of 1000.00.",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "accrue_interest",
            vault,
            vault,
            accrual_details=[accrual_details],
            account_tside=account_tside,
            effective_date=datetime(2019, 1, 1),
            event_type=ACCRUE_INTEREST,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_accrue_interest_net_postings_false_creates_postings_per_tier(self):
        vault = self.create_mock()

        payable_receivable_mapping_deposit = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_DEPOSIT_PAYABLE,
            ACCRUED_DEPOSIT_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )

        account_tside = "LIABILITY"

        accrual_details = self.run_function(
            "construct_accrual_details",
            vault,
            payable_receivable_mapping=payable_receivable_mapping_deposit,
            denomination=DEFAULT_DENOMINATION,
            balance=Decimal("3000"),
            rates={
                "tier_1": {
                    "min": Decimal("0"),
                    "max": Decimal("1000"),
                    "rate": Decimal("0.2"),
                },
                "tier_2": {
                    "min": Decimal("1000"),
                    "max": Decimal("2000"),
                    "rate": Decimal("0.1"),
                },
                "tier_3": {
                    "min": Decimal("2000"),
                    "max": Decimal("3000"),
                    "rate": Decimal("-0.1"),
                },
            },
            instruction_description="test",
            base="365",
            precision=5,
            rounding_mode=ROUND_HALF_UP,
            accrual_is_capitalised=False,
            net_postings=False,
        )

        expected_posting_calls = [
            call(
                amount=Decimal("0.54795"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_TIER_1_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_PAYABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.27397"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_TIER_2_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_DEPOSIT_PAYABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
            call(
                amount=Decimal("0.27397"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_INTEREST_TIER_3_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_DEPOSIT_RECEIVABLE_{DEFAULT_ASSET}_USD",
                from_account_id="Main account",
                from_account_address="ACCRUED_DEPOSIT_RECEIVABLE",
                to_account_id="receivable_usd",
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "test",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "accrue_interest",
            vault,
            vault,
            accrual_details=[accrual_details],
            account_tside=account_tside,
            effective_date=datetime(2019, 1, 1),
            event_type=ACCRUE_INTEREST,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_accrue_fees(self):
        vault = self.create_mock()

        payable_receivable_mapping = self.run_function(
            "construct_payable_receivable_mapping",
            vault,
            ACCRUED_OVERDRAFT_FEE_PAYABLE,
            ACCRUED_OVERDRAFT_FEE_RECEIVABLE,
            "payable_usd",
            "paid_usd",
            "receivable_usd",
            "received_usd",
        )

        account_tside = "LIABILITY"

        fee_details = self.run_function(
            "construct_fee_details",
            vault,
            payable_receivable_mapping=payable_receivable_mapping,
            denomination=DEFAULT_DENOMINATION,
            fee={"fee_1": Decimal("10")},
        )

        expected_posting_calls = [
            call(
                amount=Decimal("10"),
                denomination=DEFAULT_DENOMINATION,
                client_transaction_id=f"ACCRUE_FEES_{HOOK_EXECUTION_ID}"
                f"_ACCRUED_OVERDRAFT_FEE_PAYABLE_{DEFAULT_ASSET}_USD",
                from_account_id="payable_usd",
                from_account_address=DEFAULT_ADDRESS,
                to_account_id="Main account",
                to_account_address="ACCRUED_OVERDRAFT_FEE_PAYABLE",
                asset=DEFAULT_ASSET,
                instruction_details={
                    "description": "Accrued fee fee_1.",
                    "event": ACCRUED_OVERDRAFT_FEE,
                    "gl_impacted": "True",
                    "account_type": "",
                },
                override_all_restrictions=True,
            ),
        ]

        self.run_function(
            "accrue_fees",
            vault,
            vault,
            fee_details=[fee_details],
            account_tside=account_tside,
            event_type=ACCRUED_OVERDRAFT_FEE,
        )

        vault.make_internal_transfer_instructions.assert_has_calls(expected_posting_calls)

    def test_get_posting_instruction_details(self):
        test_cases = [
            {
                "description": "Single posting info",
                "posting_infos": [
                    PostingInfo(
                        amount=Decimal("0.1"),
                        description="Interest accrued.",
                    )
                ],
                "event_type": ACCRUE_INTEREST,
                "expected_result": {
                    "description": "Interest accrued.",
                    "event": ACCRUE_INTEREST,
                    "gl_impacted": "False",
                    "account_type": "",
                },
            },
            {
                "description": "Multiple posting infos",
                "posting_infos": [
                    PostingInfo(
                        amount=Decimal("0.1"),
                        description="Interest accrued at 5%.",
                    ),
                    PostingInfo(
                        amount=Decimal("0.2"),
                        description="Interest accrued at 10%.",
                    ),
                ],
                "event_type": "ACCRUE_TIERED_INTEREST",
                "expected_result": {
                    "description": "Aggregate of: "
                    + "Interest accrued at 5%. "
                    + "Interest accrued at 10%.",
                    "event": "ACCRUE_TIERED_INTEREST",
                    "gl_impacted": "False",
                    "account_type": "",
                },
            },
        ]
        for test_case in test_cases:
            instruction_details = self.run_function(
                "_get_posting_instruction_details",
                None,
                posting_infos=test_case["posting_infos"],
                event_type=test_case["event_type"],
            )
            self.assertEqual(
                instruction_details,
                test_case["expected_result"],
                test_case["description"],
            )
