# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.

# standard libs
from datetime import datetime
from decimal import Decimal
from typing import Optional, Union, Tuple
from json import dumps

# common
from inception_sdk.vault.contracts.types_extension import (
    Balance,
    BalanceDefaultDict,
    Tside,
    Phase,
    PostingInstructionBatch,
    Rejected,
    RejectedReason,
    Parameter,
    NumberShape,
    NumberKind,
)
from inception_sdk.test_framework.contracts.unit.common import (
    ContractTest,
    balance_dimensions,
)
from inception_sdk.test_framework.common.constants import DEFAULT_DENOMINATION

import library.features.lending.debt_management as debt_management
import library.line_of_credit.constants.files as contract_files
import library.line_of_credit.constants.addresses as address

# contract definitions
DEFAULT_DATE = datetime(2020, 1, 10)
DECIMAL_ZERO = Decimal(0)
DEFAULT_CREDIT_LIMIT = Decimal(10000)

# Dimensions
DEFAULT_DIMENSIONS = balance_dimensions()
TOTAL_PRINCIPAL_DIMENSIONS = balance_dimensions(address=address.TOTAL_PRINCIPAL)
TOTAL_INTEREST_DIMENSIONS = balance_dimensions(address=address.TOTAL_ACCRUED_INTEREST_RECEIVABLE)
TOTAL_PRINCIPAL_DUE_DIMENSIONS = balance_dimensions(address=address.TOTAL_PRINCIPAL_DUE)
TOTAL_INTEREST_DUE_DIMENSIONS = balance_dimensions(address=address.TOTAL_INTEREST_DUE)
TOTAL_PRINCIPAL_OVERDUE_DIMENSIONS = balance_dimensions(address=address.TOTAL_PRINCIPAL_OVERDUE)
TOTAL_INTEREST_OVERDUE_DIMENSIONS = balance_dimensions(address=address.TOTAL_INTEREST_OVERDUE)
TOAL_PENALTIES_DIMENSIONS = balance_dimensions(address=address.TOTAL_PENALTIES)
PENALTIES_DIMENSIONS = balance_dimensions(address=address.PENALTIES)
TOTAL_EMI_DIMENSIONS = balance_dimensions(address=address.TOTAL_EMI)


class LineOfCreditTest(ContractTest):
    contract_file = contract_files.LOC_CONTRACT
    side = Tside.ASSET
    default_denom = DEFAULT_DENOMINATION

    def create_mock(
        self,
        balance_ts=None,
        postings=None,
        creation_date=DEFAULT_DATE,
        repayment_blocking_flags=dumps(["REPAYMENT_HOLIDAY"]),
        **kwargs,
    ):
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
            repayment_blocking_flags=repayment_blocking_flags,
            # params
            denomination=self.default_denom,
            # other
            **kwargs,
        )

    def account_balances(
        self,
        dt=DEFAULT_DATE,
        balance_defs: Optional[list[dict[str, str]]] = None,
        default_committed: Union[int, str, Decimal] = DECIMAL_ZERO,
        default_pending_out: Union[int, str, Decimal] = DECIMAL_ZERO,
        default_pending_in: Union[int, str, Decimal] = DECIMAL_ZERO,
        total_principal=DECIMAL_ZERO,
        total_principal_due=DECIMAL_ZERO,
        total_principal_overdue=DECIMAL_ZERO,
        total_interest=DECIMAL_ZERO,
        total_interest_due=DECIMAL_ZERO,
        total_interest_overdue=DECIMAL_ZERO,
        # note here total penalties refer to penalties aggregated from the loans
        # whereas 'penalties' are only late payment fees accumulated on the loc
        total_penalties=DECIMAL_ZERO,
        penalties=DECIMAL_ZERO,
        total_emi=DECIMAL_ZERO,
    ) -> list[Tuple[datetime, BalanceDefaultDict]]:

        balances = BalanceDefaultDict(
            lambda: Balance(),
            {
                DEFAULT_DIMENSIONS: Balance(net=Decimal(default_committed)),
                balance_dimensions(
                    denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_OUT
                ): Balance(net=Decimal(default_pending_out)),
                balance_dimensions(
                    denomination=DEFAULT_DENOMINATION, phase=Phase.PENDING_IN
                ): Balance(net=Decimal(default_pending_in)),
                TOTAL_PRINCIPAL_DIMENSIONS: Balance(net=total_principal),
                TOTAL_PRINCIPAL_DUE_DIMENSIONS: Balance(net=total_principal_due),
                TOTAL_PRINCIPAL_OVERDUE_DIMENSIONS: Balance(net=total_principal_overdue),
                TOTAL_INTEREST_DIMENSIONS: Balance(net=total_interest),
                TOTAL_INTEREST_DUE_DIMENSIONS: Balance(net=total_interest_due),
                TOTAL_INTEREST_OVERDUE_DIMENSIONS: Balance(net=total_interest_overdue),
                TOAL_PENALTIES_DIMENSIONS: Balance(net=total_penalties),
                PENALTIES_DIMENSIONS: Balance(net=penalties),
                TOTAL_EMI_DIMENSIONS: Balance(net=total_emi),
            },
        )

        balance_defs_dict = self.init_balances(dt, balance_defs)[0][1]

        return [(dt, balances + balance_defs_dict)]


class PrePostingCodeTest(LineOfCreditTest):
    def setUp(self):
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE,
            default_committed=Decimal("0"),
        )
        self.mock_vault = self.create_mock(
            balance_ts=balance_ts,
        )

    def test_repayment_with_excess_precision_rejected(self):
        postings = PostingInstructionBatch(
            posting_instructions=[self.inbound_hard_settlement(Decimal("370.381"))]
        )

        with self.assertRaises(Rejected) as ctx:
            self.run_function("pre_posting_code", self.mock_vault, postings, DEFAULT_DATE)

        self.assertEqual(
            ctx.exception.message,
            "Amount 370.381 has non-zero digits after 2 decimal places",
        )

    def test_multiple_postings_rejected(self):

        postings = PostingInstructionBatch(
            posting_instructions=[
                self.inbound_hard_settlement(Decimal("370.38")),
                self.inbound_hard_settlement(Decimal("370.38")),
            ]
        )

        with self.assertRaises(Rejected) as ctx:
            self.run_function("pre_posting_code", self.mock_vault, postings, DEFAULT_DATE)

        self.assertEqual(
            ctx.exception.message,
            "Only batches with a single hard settlement are supported",
        )

    def test_pre_posting_rejects_posting_batch_when_blocking_flag_applied(self):
        mock_vault = self.create_mock(flags=["REPAYMENT_HOLIDAY"])

        postings = [
            self.inbound_hard_settlement(amount=501, denomination="GBP"),
        ]

        pib = self.mock_posting_instruction_batch(
            posting_instructions=postings, value_timestamp=DEFAULT_DATE
        )
        with self.assertRaises(Rejected) as e:
            self.run_function(
                "pre_posting_code",
                mock_vault,
                postings=pib,
                effective_date=DEFAULT_DATE,
            )
        self.assertEqual(e.exception.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(str(e.exception), "Repayments blocked for this account")
        self.assert_no_side_effects(mock_vault)

    def test_pre_posting_allows_posting_with_override(self):
        # combines multiple conditions that would normally result in rejections
        mock_vault = self.create_mock(flags=["REPAYMENT_HOLIDAY"])
        pib = self.mock_posting_instruction_batch(
            posting_instructions=[
                self.inbound_hard_settlement(Decimal("370.381")),
                self.inbound_hard_settlement(Decimal("370.38")),
            ],
            batch_details={"force_override": "true"},
        )

        result = self.run_function(
            "pre_posting_code",
            mock_vault,
            postings=pib,
            effective_date=DEFAULT_DATE,
        )

        self.assertIsNone(result)


class FeatureIntegrationTest(LineOfCreditTest):
    def test_execution_schedules(self):
        mock_vault = self.create_mock(
            due_amount_calculation_day=5,
            due_amount_calculation_hour=4,
            due_amount_calculation_minute=5,
            due_amount_calculation_second=6,
        )
        schedules = self.run_function("execution_schedules", mock_vault)
        self.assertListEqual(
            schedules,
            [
                (
                    debt_management.DUE_AMOUNT_CALCULATION,
                    {
                        "day": "5",
                        "hour": "4",
                        "minute": "5",
                        "second": "6",
                    },
                ),
            ],
        )


class DerivedParametersTest(LineOfCreditTest):
    def create_mock(
        self,
        creation_date=DEFAULT_DATE,
        loc_start_date=DEFAULT_DATE,
        credit_limit=Decimal("1000"),
        repayment_period=3,
        due_amount_calculation_day=5,
        due_amount_calculation_hour=4,
        due_amount_calculation_minute=5,
        due_amount_calculation_second=6,
        overpayment_fee_percentage=Decimal("0.05"),
        **kwargs,
    ):
        return super().create_mock(
            creation_date=creation_date,
            loc_start_date=loc_start_date,
            repayment_period=repayment_period,
            due_amount_calculation_day=due_amount_calculation_day,
            due_amount_calculation_hour=due_amount_calculation_hour,
            due_amount_calculation_minute=due_amount_calculation_minute,
            due_amount_calculation_second=due_amount_calculation_second,
            credit_limit=credit_limit,
            overpayment_fee_percentage=overpayment_fee_percentage,
            **kwargs,
        )

    def test_next_repayment_date_str(self):
        mock_vault = self.create_mock()
        result = self.run_function(
            "derived_parameters",
            mock_vault,
            DEFAULT_DATE,
        )
        self.assertEqual(result["next_repayment_date"], "2020-03-08 04:05:06")

    def test_total_outstanding_due(self):
        total_outstanding_due = Decimal("104.23")
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE,
            total_principal_due=Decimal("97.47"),
            total_interest_due=Decimal("6.76"),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
        )

        result = self.run_function(
            "derived_parameters",
            mock_vault,
            DEFAULT_DATE,
        )

        self.assertEqual(result["total_outstanding_due"], total_outstanding_due)

    def test_total_arrears(self):
        total_arrears = Decimal("104.23")
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE,
            total_principal_overdue=Decimal("97.47"),
            total_interest_overdue=Decimal("6.76"),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
        )

        result = self.run_function(
            "derived_parameters",
            mock_vault,
            DEFAULT_DATE,
        )

        self.assertEqual(result["total_arrears"], total_arrears)

    def test_total_outstanding_principal_and_total_available_credit(self):
        credit_limit = Decimal("1000")
        total_outstanding_principal = Decimal("104.23")
        total_available_credit = credit_limit - total_outstanding_principal

        balance_ts = self.account_balances(
            dt=DEFAULT_DATE,
            total_principal=Decimal("77.47"),
            total_principal_due=Decimal("14.63"),
            total_principal_overdue=Decimal("12.13"),
        )
        mock_vault = self.create_mock(balance_ts=balance_ts)

        result = self.run_function(
            "derived_parameters",
            mock_vault,
            DEFAULT_DATE,
        )

        self.assertEqual(result["total_outstanding_principal"], total_outstanding_principal)
        self.assertEqual(result["total_available_credit"], total_available_credit)

    def test_total_monthly_repayment(self):
        total_emi = Decimal("253.24")
        balance_ts = self.account_balances(
            dt=DEFAULT_DATE,
            total_emi=Decimal("253.24"),
        )
        mock_vault = self.create_mock(
            balance_ts=balance_ts,
        )

        result = self.run_function(
            "derived_parameters",
            mock_vault,
            DEFAULT_DATE,
        )

        self.assertEqual(result["total_monthly_repayment"], total_emi)

    def test_total_early_repayment(self):
        early_repayment_amount = Decimal("799")
        overpayment_fees = round(Decimal(99 * 0.05), 2)
        total_early_repayment_amount = early_repayment_amount + overpayment_fees

        balance_ts = self.account_balances(
            dt=DEFAULT_DATE,
            total_principal=Decimal("99"),
            total_principal_due=Decimal("100"),
            total_principal_overdue=Decimal("100"),
            total_interest=Decimal("100"),
            total_interest_due=Decimal("100"),
            total_interest_overdue=Decimal("100"),
            total_penalties=Decimal("100"),
            penalties=Decimal("100"),
        )
        mock_vault = self.create_mock(balance_ts=balance_ts)

        result = self.run_function(
            "derived_parameters",
            mock_vault,
            DEFAULT_DATE,
        )

        self.assertEqual(result["total_early_repayment_amount"], total_early_repayment_amount)


class PreParameterChangeTest(LineOfCreditTest):
    def test_credit_limit_param_shape_updated_to_reflect_usage(self):
        # total outstanding should just be 3
        mock_vault = self.create_mock(
            balance_ts=self.account_balances(
                total_principal=Decimal("1"),
                total_principal_due=Decimal("1"),
                total_principal_overdue=Decimal("1"),
                # these are just here to ensure we exclude them
                total_interest_due=Decimal("100"),
                total_emi=Decimal("100"),
                total_interest_overdue=Decimal("100"),
            )
        )
        credit_limit_param = Parameter(
            name="credit_limit",
            shape=NumberShape(
                kind=NumberKind.MONEY,
                min_value=0,
                step=0.01,
            ),
        )
        parameters = {"credit_limit": credit_limit_param}
        effective_date = datetime(2020, 2, 1, 3, 4, 5)
        parameters = self.run_function(
            "pre_parameter_change_code",
            mock_vault,
            parameters,
            effective_date,
        )
        self.assertEqual(parameters["credit_limit"].shape.min_value, 3)
