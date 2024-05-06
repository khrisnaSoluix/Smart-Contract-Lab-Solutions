# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
# standard

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR, ROUND_HALF_DOWN

# common
from inception_sdk.test_framework.contracts.unit.common import (
    ContractModuleTest,
)

CONTRACT_MODULE_FILE = "library/common/contract_modules/amortisation.py"
DEFAULT_DATE = datetime(2021, 1, 1)
DEFAULT_DENOMINATION = "GBP"
DEFAULT_ADDRESS = "DEFAULT"
OVERPAYMENT_ADDRESS = "OVERPAYMENT"
DEFAULT_ASSET = "COMMERCIAL_BANK_MONEY"


class AmortisationModuleTest(ContractModuleTest):
    contract_module_file = CONTRACT_MODULE_FILE

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

    def construct_declining_principal_input_object_with_default_values(
        self,
        vault,
        is_last_payment_date: bool,
        monthly_interest_rate: Decimal,
        accrued_interest_excluding_overpayment: Decimal,
        actual_principal: Decimal,
        interest_accrued: Decimal = Decimal("1.5"),
        precision: int = int(2),
        remaining_term: int = int("0"),
        principal_with_capitalised_interest=Decimal("2000"),
        predefined_emi: bool = False,
        emi: Decimal = Decimal("0"),
        principal_excess: Decimal = Decimal("1.1"),
        accrued_additional_interest: Decimal = Decimal("0"),
        holiday_impact_preference: str = "DO_NOT_INCREASE_EMI",
        overpayment_impact_preference: str = "reduce_term",
        previous_due_amount_blocked: bool = True,
        previous_overpayment_amount: Decimal = Decimal("0"),
        current_overpayment_amount: Decimal = Decimal("0"),
        was_previous_interest_rate_fixed=True,
        is_current_interest_rate_fixed=True,
        previous_repayment_day_schedule_date=None,
        last_rate_change_date=datetime(2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc),
        lump_sum_amount: Decimal = Decimal("0"),
    ):

        emi_calc_input = self.run_function(
            "construct_emi_recalculation_condition_input",
            vault,
            holiday_impact_preference=holiday_impact_preference,
            overpayment_impact_preference=overpayment_impact_preference,
            previous_due_amount_blocked=previous_due_amount_blocked,
            previous_overpayment_amount=previous_overpayment_amount,
            was_previous_interest_rate_fixed=was_previous_interest_rate_fixed,
            is_current_interest_rate_fixed=is_current_interest_rate_fixed,
            previous_repayment_day_schedule_date=previous_repayment_day_schedule_date,
            last_rate_change_date=last_rate_change_date,
        )

        return self.run_function(
            "construct_declining_principal_amortisation_input",
            vault,
            precision=precision,
            actual_principal=actual_principal,
            principal_with_capitalised_interest=principal_with_capitalised_interest,
            remaining_term=remaining_term,
            monthly_interest_rate=monthly_interest_rate,
            emi=emi,
            current_overpayment_amount=current_overpayment_amount,
            is_last_payment_date=is_last_payment_date,
            principal_excess=principal_excess,
            interest_accrued=interest_accrued,
            accrued_interest_excluding_overpayment=accrued_interest_excluding_overpayment,
            accrued_additional_interest=accrued_additional_interest,
            emi_recalculation_condition=emi_calc_input,
            lump_sum_amount=lump_sum_amount,
            predefined_emi=predefined_emi,
        )

    def test_construct_emi_recalculation_input(self):
        holiday_impact_preference = "INCREASE_EMI"
        overpayment_impact_preference = "REDUCE_EMI"
        previous_due_amount_blocked = True
        previous_overpayment_amount = Decimal("100.2")
        was_previous_interest_rate_fixed = False
        is_current_interest_rate_fixed = True
        previous_repayment_day_schedule_date = None
        last_rate_change_date = datetime(2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc)

        result = self.run_function(
            "construct_emi_recalculation_condition_input",
            self.create_mock(),
            holiday_impact_preference=holiday_impact_preference,
            overpayment_impact_preference=overpayment_impact_preference,
            previous_due_amount_blocked=previous_due_amount_blocked,
            previous_overpayment_amount=previous_overpayment_amount,
            was_previous_interest_rate_fixed=was_previous_interest_rate_fixed,
            is_current_interest_rate_fixed=is_current_interest_rate_fixed,
            previous_repayment_day_schedule_date=previous_repayment_day_schedule_date,
            last_rate_change_date=last_rate_change_date,
        )

        self.assertTrue(isinstance(result, tuple))
        self.assertEqual(result.holiday_impact_preference, holiday_impact_preference)
        self.assertEqual(result.overpayment_impact_preference, overpayment_impact_preference)
        self.assertEqual(result.previous_due_amount_blocked, previous_due_amount_blocked)
        self.assertEqual(result.previous_overpayment_amount, previous_overpayment_amount)
        self.assertEqual(result.was_previous_interest_rate_fixed, was_previous_interest_rate_fixed)
        self.assertEqual(result.is_current_interest_rate_fixed, is_current_interest_rate_fixed)
        self.assertEqual(
            result.previous_repayment_day_schedule_date,
            previous_repayment_day_schedule_date,
        )
        self.assertEqual(result.last_rate_change_date, last_rate_change_date)

    def test_construct_declining_principal_amortisation_input(self):
        precision = int(5)
        actual_principal = Decimal("20.77")
        principal_with_capitalised_interest = Decimal("100.90")
        remaining_term = Decimal("10")
        monthly_interest_rate = Decimal("1.1135")
        emi = Decimal("300.56")
        current_overpayment_amount = Decimal("0")
        is_last_payment_date = True
        principal_excess = Decimal("600.6")
        interest_accrued = Decimal("45.99")
        accrued_interest_excluding_overpayment = Decimal("100.1")
        accrued_additional_interest = Decimal("100")
        emi_recalculation_condition = "SomeMappingNamedTuple"
        lump_sum_amount = Decimal("10")

        result = self.run_function(
            "construct_declining_principal_amortisation_input",
            self.create_mock(),
            precision=precision,
            actual_principal=actual_principal,
            principal_with_capitalised_interest=principal_with_capitalised_interest,
            remaining_term=remaining_term,
            monthly_interest_rate=monthly_interest_rate,
            emi=emi,
            current_overpayment_amount=current_overpayment_amount,
            is_last_payment_date=is_last_payment_date,
            principal_excess=principal_excess,
            interest_accrued=interest_accrued,
            accrued_interest_excluding_overpayment=accrued_interest_excluding_overpayment,
            accrued_additional_interest=accrued_additional_interest,
            emi_recalculation_condition=emi_recalculation_condition,
            lump_sum_amount=lump_sum_amount,
        )

        self.assertTrue(isinstance(result, tuple))
        self.assertEqual(result.precision, int(5))
        self.assertEqual(result.remaining_term, Decimal("10"))
        self.assertEqual(result.monthly_interest_rate, Decimal("1.1135"))
        self.assertEqual(result.emi, Decimal("300.56"))
        self.assertEqual(result.current_overpayment_amount, Decimal("0"))
        self.assertEqual(result.principal_with_capitalised_interest, Decimal("100.90"))
        self.assertEqual(result.is_last_payment_date, True)
        self.assertEqual(result.principal_excess, Decimal("600.6"))
        self.assertEqual(result.interest_accrued, Decimal("45.99"))
        self.assertEqual(result.accrued_interest_excluding_overpayment, Decimal("100.1"))
        self.assertEqual(result.accrued_additional_interest, Decimal("100"))
        self.assertEqual(result.emi_recalculation_condition, "SomeMappingNamedTuple")
        self.assertEqual(result.lump_sum_amount, Decimal("10"))

    def test_calculate_declining_principal_emi(self):
        test_cases = [
            {
                "description": "lump sum amount is 0",
                "precision": int(2),
                "remaining_principal": Decimal("100"),
                "monthly_interest_rate": Decimal("0.02"),
                "remaining_term": Decimal("2"),
                "lump_sum_amount": Decimal("0"),
                "expected_result": Decimal("51.50"),
            },
            {
                "description": "lump sum amount is None",
                "precision": int(2),
                "remaining_principal": Decimal("100"),
                "monthly_interest_rate": Decimal("0.02"),
                "remaining_term": Decimal("2"),
                "lump_sum_amount": None,
                "expected_result": Decimal("51.50"),
            },
            {
                "description": "lump sum amount is non-0",
                "precision": int(2),
                "remaining_principal": Decimal("100000"),
                "monthly_interest_rate": Decimal("0.02") / Decimal("12"),
                "remaining_term": int(36),
                "lump_sum_amount": Decimal("50000"),
                "expected_result": Decimal("1515.46"),
            },
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock()
            # (100*0.02)*((1+0.02)^2)/(((1+0.02)^1)-1) = 51.50
            result = self.run_function(
                "_calculate_declining_principal_emi",
                mock_vault,
                precision=test_case["precision"],
                remaining_principal=test_case["remaining_principal"],
                monthly_interest_rate=test_case["monthly_interest_rate"],
                remaining_term=test_case["remaining_term"],
                lump_sum_amount=test_case["lump_sum_amount"],
            )
            self.assertEqual(result, test_case["expected_result"])

    def test_get_remaining_principal(self):

        test_cases = [
            {
                "description": "returns actual_principal as there have been overpayments and want"
                "to reduce the EMI",
                "actual_principal": Decimal("10"),
                "principal_with_capitalised_interest": Decimal("20"),
                "overpayment_impact_preference": "REDUCE_EMI",
                "current_overpayment_amount": 10,
                "expected_result": Decimal("10"),
            },
            {
                "description": "returns principal with capitalised interest as there are no"
                "current overpayments that need to be taken into account"
                "balance is 0",
                "actual_principal": Decimal("10"),
                "principal_with_capitalised_interest": Decimal("20"),
                "overpayment_impact_preference": "REDUCE_EMI",
                "current_overpayment_amount": 0,
                "expected_result": Decimal("20"),
            },
            {
                "description": "returns principal with capitalised interest as the overpayment"
                "impact preference is to increase the EMI - rather than REDUCE_EMI",
                "actual_principal": Decimal("10"),
                "principal_with_capitalised_interest": Decimal("20"),
                "overpayment_impact_preference": "INCREASE_EMI",
                "current_overpayment_amount": 10,
                "expected_result": Decimal("20"),
            },
        ]

        for test_case in test_cases:

            mock_vault = self.create_mock()
            result = self.run_function(
                "_get_remaining_principal",
                mock_vault,
                actual_principal=test_case["actual_principal"],
                principal_with_capitalised_interest=test_case[
                    "principal_with_capitalised_interest"
                ],
                overpayment_impact_preference=test_case["overpayment_impact_preference"],
                current_overpayment_amount=test_case["current_overpayment_amount"],
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_has_rate_changed_since_last_repayment_date(self):
        test_cases = [
            {
                "description": "interest loan rate has not changed since last repayment date",
                "was_previous_interest_rate_fixed": False,
                "is_current_interest_rate_fixed": False,
                "last_repayment_day_schedule_event": datetime(
                    2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc
                ),
                "last_rate_change_date": datetime(2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc),
                "expected_result": False,
            },
            {
                "description": "the last_rate_change_date > last_repayment_sch_event meaning the"
                "rate has changed since the last repayment date",
                "was_previous_interest_rate_fixed": False,
                "is_current_interest_rate_fixed": False,
                "last_repayment_day_schedule_event": datetime(
                    2020, 2, 20, 0, 0, 2, tzinfo=timezone.utc
                ),
                "last_rate_change_date": datetime(2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc),
                "expected_result": True,
            },
            {
                "description": "There has been a change in rate as the interest loan rate was "
                "previously a fixed rate but the rate is now not fixed",
                "was_previous_interest_rate_fixed": True,
                "is_current_interest_rate_fixed": False,
                "last_repayment_day_schedule_event": datetime(
                    2020, 2, 20, 0, 0, 2, tzinfo=timezone.utc
                ),
                "last_rate_change_date": datetime(2020, 2, 20, 0, 0, 2, tzinfo=timezone.utc),
                "expected_result": True,
            },
        ]
        for test_case in test_cases:

            mock_vault = self.create_mock()
            result = self.run_function(
                "_has_rate_changed_since_last_repayment_date",
                mock_vault,
                was_previous_interest_rate_fixed=test_case["was_previous_interest_rate_fixed"],
                is_current_interest_rate_fixed=test_case["is_current_interest_rate_fixed"],
                previous_repayment_day_schedule_date=test_case["last_repayment_day_schedule_event"],
                last_rate_change_date=test_case["last_rate_change_date"],
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_does_account_have_new_overpayment(self):

        test_cases = [
            {
                "description": "Previous and current overpayments balances are equal"
                "- no new overpayments",
                "previous_overpayment_amount": Decimal("10"),
                "current_overpayment_amount": Decimal("10"),
                "expected_result": False,
            },
            {
                "description": "Previous and current overpayments are not"
                "equal so a new overpayment has occured",
                "previous_overpayment_amount": Decimal("50"),
                "current_overpayment_amount": Decimal("40"),
                "expected_result": True,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock()
            result = self.run_function(
                "_does_account_have_new_overpayment",
                mock_vault,
                previous_overpayment_amount=test_case["previous_overpayment_amount"],
                current_overpayment_amount=test_case["current_overpayment_amount"],
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_does_emi_need_recalculation(self):

        test_cases = [
            {
                "description": "EMI should be recalculated as emi = 0 meaning"
                "it has not been previously calculated",
                "emi": 0,
                "holiday_impact_preference": "holiday impact",
                "overpayment_impact_preference": "overpayment impact",
                "previous_due_amount_blocked": True,
                "previous_overpayment_amount": Decimal("0.4"),
                "current_overpayment_amount": Decimal("0.4"),
                "was_previous_interest_rate_fixed": True,
                "is_current_interest_rate_fixed": True,
                "previous_repayment_day_schedule_date": None,
                "last_rate_change_date": datetime(2020, 2, 20, 0, 0, 2, tzinfo=timezone.utc),
                "predefined_emi": False,
                "expected_result": True,
            },
            {
                "description": "EMI should be recalculated as the interest "
                "rate is variable and has changed since the last repayment date",
                "emi": 10,
                "holiday_impact_preference": "holiday ",
                "overpayment_impact_preference": "impact",
                "previous_due_amount_blocked": True,
                "previous_overpayment_amount": Decimal("0.4"),
                "current_overpayment_amount": Decimal("0.4"),
                "was_previous_interest_rate_fixed": True,
                "is_current_interest_rate_fixed": False,
                "previous_repayment_day_schedule_date": datetime(
                    2020, 2, 20, 0, 0, 1, tzinfo=timezone.utc
                ),
                "last_rate_change_date": datetime(2020, 2, 20, 0, 0, 2, tzinfo=timezone.utc),
                "predefined_emi": False,
                "expected_result": True,
            },
            {
                "description": "EMI should be recalculated as the EMI is being"
                "increased following a repayment holiday",
                "emi": 10,
                "holiday_impact_preference": "INCREASE_EMI",
                "overpayment_impact_preference": "impact",
                "previous_due_amount_blocked": True,
                "previous_overpayment_amount": Decimal("0.4"),
                "current_overpayment_amount": Decimal("0.4"),
                "was_previous_interest_rate_fixed": True,
                "is_current_interest_rate_fixed": False,
                "previous_repayment_day_schedule_date": datetime(
                    2020, 2, 20, 0, 0, 3, tzinfo=timezone.utc
                ),
                "last_rate_change_date": datetime(2020, 2, 20, 0, 0, 2, tzinfo=timezone.utc),
                "predefined_emi": False,
                "expected_result": True,
            },
            {
                "description": "EMI should be recalculated as the EMI is being"
                "reduced following an overpayment",
                "emi": 10,
                "holiday_impact_preference": "NOT_INCREASE_EMI",
                "overpayment_impact_preference": "REDUCE_EMI",
                "previous_due_amount_blocked": True,
                "previous_overpayment_amount": Decimal("0.4"),
                "current_overpayment_amount": Decimal("0.5"),
                "was_previous_interest_rate_fixed": True,
                "is_current_interest_rate_fixed": False,
                "previous_repayment_day_schedule_date": None,
                "last_rate_change_date": datetime(2020, 2, 20, 0, 0, 2, tzinfo=timezone.utc),
                "predefined_emi": False,
                "expected_result": True,
            },
            {
                "description": "EMI does not need to be recalculated",
                "emi": 10,
                "holiday_impact_preference": "NOT_INCREASE_EMI",
                "overpayment_impact_preference": "NOT_REDUCE_EMI",
                "previous_due_amount_blocked": False,
                "previous_overpayment_amount": Decimal("0.4"),
                "current_overpayment_amount": Decimal("0.4"),
                "was_previous_interest_rate_fixed": True,
                "is_current_interest_rate_fixed": True,
                "previous_repayment_day_schedule_date": datetime(
                    2020, 2, 22, 0, 0, 10, tzinfo=timezone.utc
                ),
                "last_rate_change_date": datetime(2020, 2, 20, 0, 0, 2, tzinfo=timezone.utc),
                "predefined_emi": False,
                "expected_result": False,
            },
            {
                "description": "EMI should never be recalculated as is fixed",
                "emi": 10,
                "holiday_impact_preference": "INCREASE_EMI",
                "overpayment_impact_preference": "REDUCE_EMI",
                "previous_due_amount_blocked": True,
                "previous_overpayment_amount": Decimal("0.4"),
                "current_overpayment_amount": Decimal("0.4"),
                "was_previous_interest_rate_fixed": True,
                "is_current_interest_rate_fixed": False,
                "previous_repayment_day_schedule_date": datetime(
                    2020, 2, 22, 0, 0, 10, tzinfo=timezone.utc
                ),
                "last_rate_change_date": datetime(2020, 2, 20, 0, 0, 2, tzinfo=timezone.utc),
                "predefined_emi": True,
                "expected_result": False,
            },
            {
                "description": "EMI should not be recalculated as there is no previous repayment "
                "day schedule date. This is not an expected real-life scenario, but this ensures "
                "that we do not check for changing rates when no schedule has run yet.",
                "emi": 20,
                "holiday_impact_preference": "holiday impact",
                "overpayment_impact_preference": "overpayment impact",
                "previous_due_amount_blocked": True,
                "previous_overpayment_amount": Decimal("0.4"),
                "current_overpayment_amount": Decimal("0.4"),
                "was_previous_interest_rate_fixed": True,
                "is_current_interest_rate_fixed": True,
                "previous_repayment_day_schedule_date": None,
                "last_rate_change_date": datetime(2020, 2, 20, 0, 0, 2, tzinfo=timezone.utc),
                "predefined_emi": False,
                "expected_result": False,
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock()
            emi_calc_input = self.run_function(
                "construct_emi_recalculation_condition_input",
                mock_vault,
                holiday_impact_preference=test_case["holiday_impact_preference"],
                overpayment_impact_preference=test_case["overpayment_impact_preference"],
                previous_due_amount_blocked=test_case["previous_due_amount_blocked"],
                previous_overpayment_amount=test_case["previous_overpayment_amount"],
                was_previous_interest_rate_fixed=test_case["was_previous_interest_rate_fixed"],
                is_current_interest_rate_fixed=test_case["is_current_interest_rate_fixed"],
                previous_repayment_day_schedule_date=test_case[
                    "previous_repayment_day_schedule_date"
                ],
                last_rate_change_date=test_case["last_rate_change_date"],
            )

            result = self.run_function(
                "_does_emi_need_recalculation",
                mock_vault,
                emi_calc_input=emi_calc_input,
                emi=test_case["emi"],
                current_overpayment_amount=test_case["current_overpayment_amount"],
                predefined_emi=test_case["predefined_emi"],
            )

            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_calculate_declining_principal_repayment(self):

        test_cases = [
            {
                "description": "The remaining term is <=0 - lifetime of loan "
                "has finished but remaining principal needs to be paid off so "
                "emi = actual_principal (no recalc required)",
                "monthly_interest_rate": Decimal("0.025"),
                "actual_principal": Decimal("5.5"),
                "interest_accrued": Decimal("1.5"),
                "remaining_term": 0,
                "predefined_emi": False,
                "emi": Decimal("100"),
                "is_last_payment_date": True,
                "accrued_interest_excluding_overpayment": Decimal("1.40"),
                "expected_result_emi": Decimal("5.5"),
                "expected_result_interest": Decimal("1.5"),
                "expected_result_accrued_interest": Decimal("1.5"),
                "expected_result_accrued_interest_excluding_overpayment": Decimal("1.4"),
                "expected_result_principal_due": Decimal("5.5"),
                "expected_result_principal_excess": Decimal("1.1"),
            },
            {
                "description": "As the interest rate is 0, the EMI is = principal_due"
                "(no recalc required)",
                "monthly_interest_rate": Decimal("0"),
                "actual_principal": Decimal("5.5"),
                "interest_accrued": Decimal("1.5"),
                "remaining_term": 10,
                "predefined_emi": False,
                "emi": 100,
                "is_last_payment_date": True,
                "accrued_interest_excluding_overpayment": Decimal("1.4"),
                "expected_result_emi": Decimal("0.55"),
                "expected_result_interest": Decimal("1.5"),
                "expected_result_accrued_interest": Decimal("1.5"),
                "expected_result_accrued_interest_excluding_overpayment": Decimal("1.4"),
                # actual_principal/remaining_term 5.5/10
                "expected_result_principal_due": Decimal("0.55"),
                "expected_result_principal_excess": Decimal("1.1"),
            },
            {
                "description": "EMI does not require a recalculation"
                "principal_due = 100-1.4-0 = 98.5. As principal_due > actual_principal"
                "principal_due = actual_principal = 10.5 & principal_excess = 0",
                "monthly_interest_rate": Decimal("0.025"),
                "actual_principal": Decimal("10.5"),
                "interest_accrued": Decimal("1.5"),
                "remaining_term": 10,
                "predefined_emi": False,
                "emi": Decimal("100"),
                "is_last_payment_date": False,
                "accrued_interest_excluding_overpayment": Decimal("10.5"),
                "expected_result_emi": Decimal("100"),
                "expected_result_interest": Decimal("1.5"),
                "expected_result_accrued_interest": Decimal("1.5"),
                "expected_result_accrued_interest_excluding_overpayment": Decimal("10.5"),
                "expected_result_principal_due": Decimal("10.5"),
                "expected_result_principal_excess": Decimal("0"),
            },
            {
                "description": "EMI requires re-calculation, no lump sum",
                "monthly_interest_rate": Decimal("0.00025"),
                "actual_principal": Decimal("100000"),
                "remaining_term": 36,
                "emi": Decimal("0"),
                "predefined_emi": False,
                "interest_accrued": Decimal("1.5"),
                "is_last_payment_date": False,
                "accrued_interest_excluding_overpayment": Decimal("1.5"),
                # emi = 2000*0.00025((1.00025^36)/((1.00025^36) - 1)) = 55.81 (2dp)
                # 2000 = principal_with_capitalised_interest in default values
                "expected_result_emi": Decimal("55.81"),
                "expected_result_interest": Decimal("1.5"),
                "expected_result_accrued_interest": Decimal("1.5"),
                "expected_result_accrued_interest_excluding_overpayment": Decimal("1.5"),
                "expected_result_principal_due": Decimal("54.31"),
                "expected_result_principal_excess": Decimal("0.00"),
            },
            {
                "description": "EMI requires re-calculation, lump sum provided",
                "monthly_interest_rate": Decimal("0.02") / Decimal("12"),
                "actual_principal": Decimal("1000"),
                "remaining_term": 36,
                "interest_accrued": Decimal("1.5"),
                "emi": Decimal("0"),
                "predefined_emi": False,
                "is_last_payment_date": False,
                "accrued_interest_excluding_overpayment": Decimal("1.5"),
                "lump_sum_amount": Decimal("50"),
                "expected_result_emi": Decimal("55.94"),
                "expected_result_interest": Decimal("1.5"),
                "expected_result_accrued_interest": Decimal("1.5"),
                "expected_result_accrued_interest_excluding_overpayment": Decimal("1.5"),
                # 55.94-1.5-0 = 54.44
                "expected_result_principal_due": Decimal("54.44"),
                "expected_result_principal_excess": Decimal("0"),
            },
            {
                "description": "Fixed EMI greater than Interest",
                "monthly_interest_rate": Decimal("0.025"),
                "actual_principal": Decimal("100000"),
                "interest_accrued": Decimal("100"),
                "remaining_term": 10,
                "predefined_emi": True,
                "emi": Decimal("250"),
                "is_last_payment_date": False,
                "accrued_interest_excluding_overpayment": Decimal("100"),
                # emi = fixed at 250
                "expected_result_emi": Decimal("250"),
                "expected_result_interest": Decimal("100"),
                "expected_result_accrued_interest": Decimal("100"),
                "expected_result_accrued_interest_excluding_overpayment": Decimal("100"),
                # 250 - 100 = 150
                "expected_result_principal_due": Decimal("150"),
                "expected_result_principal_excess": Decimal("0"),
            },
            {
                "description": "Fixed EMI less than Interest",
                "monthly_interest_rate": Decimal("0.025"),
                "actual_principal": Decimal("100000"),
                "interest_accrued": Decimal("100"),
                "remaining_term": 10,
                "predefined_emi": True,
                "emi": Decimal("2"),
                "is_last_payment_date": False,
                "accrued_interest_excluding_overpayment": Decimal("100"),
                # emi = fixed at 2.00
                "expected_result_emi": Decimal("2"),
                "expected_result_interest": Decimal("2"),
                # Used to flatten out interest to 2dp, but for this case only at final repayment
                "expected_result_accrued_interest": Decimal("100"),
                "expected_result_accrued_interest_excluding_overpayment": Decimal("2"),
                # overwrite as 0
                "expected_result_principal_due": Decimal("0"),
                # overwrite as 0
                "expected_result_principal_excess": Decimal("0"),
            },
        ]

        for test_case in test_cases:
            mock_vault = self.create_mock()
            input_values = {
                "vault": mock_vault,
                "accrued_interest_excluding_overpayment": test_case[
                    "accrued_interest_excluding_overpayment"
                ],
                "actual_principal": test_case["actual_principal"],
                "interest_accrued": test_case["interest_accrued"],
                "remaining_term": test_case["remaining_term"],
                "emi": test_case["emi"],
                "is_last_payment_date": test_case["is_last_payment_date"],
                "monthly_interest_rate": test_case["monthly_interest_rate"],
                "predefined_emi": test_case["predefined_emi"],
            }

            if "lump_sum_amount" in test_case:
                input_values["lump_sum_amount"] = test_case["lump_sum_amount"]

            declining_principal_input = (
                self.construct_declining_principal_input_object_with_default_values(**input_values)
            )

            result = self.run_function(
                "calculate_declining_principal_repayment",
                mock_vault,
                declining_principal_input,
            )
            self.assertEqual(
                result["emi"],
                test_case["expected_result_emi"],
                test_case["description"],
            ),
            self.assertEqual(
                result["accrued_interest"],
                test_case["expected_result_accrued_interest"],
                test_case["description"],
            )
            self.assertEqual(
                result["accrued_interest_excluding_overpayment"],
                test_case["expected_result_accrued_interest_excluding_overpayment"],
                test_case["description"],
            )
            self.assertEqual(
                result["principal_due_excluding_overpayment"],
                test_case["expected_result_principal_due"],
                test_case["description"],
            )
            self.assertEqual(
                result["principal_excess"],
                test_case["expected_result_principal_excess"],
                test_case["description"],
            )

    def test_construct_interest_only_amortisation_input(self):

        remaining_principal = Decimal("1.23456")
        accrued_interest = Decimal("2.34567")
        accrued_interest_excluding_overpayment = Decimal("1.23456")
        precision = int(2)
        is_last_repayment_date = True

        result = self.run_function(
            "construct_interest_only_amortisation_input",
            vault_object=None,
            remaining_principal=remaining_principal,
            accrued_interest=accrued_interest,
            accrued_interest_excluding_overpayment=accrued_interest_excluding_overpayment,
            precision=precision,
            is_last_repayment_date=is_last_repayment_date,
        )

        self.assertTrue(isinstance(result, tuple))
        self.assertEqual(result.remaining_principal, remaining_principal)
        self.assertEqual(result.accrued_interest, accrued_interest)
        self.assertEqual(
            result.accrued_interest_excluding_overpayment,
            accrued_interest_excluding_overpayment,
        )
        self.assertEqual(result.precision, precision)
        self.assertEqual(result.is_last_repayment_date, is_last_repayment_date)
        self.assertEqual(len(result.__annotations__.keys()), 5)

    def test_calculate_interest_only_repayment(self):
        amortisation_input = self.run_function(
            "construct_interest_only_amortisation_input",
            vault_object=None,
            remaining_principal=Decimal("200000"),
            accrued_interest=Decimal("123.4567"),
            accrued_interest_excluding_overpayment=Decimal("123.4567"),
            precision=2,
            is_last_repayment_date=False,
        )

        result = self.run_function(
            "calculate_interest_only_repayment",
            vault_object=None,
            amortisation_input=amortisation_input,
        )
        self.assertEqual(result["emi"], Decimal("0"))
        self.assertEqual(result["interest_due"], Decimal("123.46"))
        self.assertEqual(result["accrued_interest"], Decimal("123.4567"))
        self.assertEqual(result["accrued_interest_excluding_overpayment"], Decimal("123.4567"))
        self.assertEqual(result["principal_due_excluding_overpayment"], Decimal("0"))
        self.assertEqual(result["principal_excess"], Decimal("0"))

    def test_calculate_interest_only_last_repayment(self):
        amortisation_input = self.run_function(
            "construct_interest_only_amortisation_input",
            vault_object=None,
            remaining_principal=Decimal("300000"),
            accrued_interest=Decimal("123.4567"),
            accrued_interest_excluding_overpayment=Decimal("123.4567"),
            precision=int(2),
            is_last_repayment_date=True,
        )

        result = self.run_function(
            "calculate_interest_only_repayment",
            vault_object=None,
            amortisation_input=amortisation_input,
        )
        self.assertEqual(result["emi"], Decimal("0"))
        self.assertEqual(result["interest_due"], Decimal("123.46"))
        self.assertEqual(result["accrued_interest"], Decimal("123.4567"))
        self.assertEqual(result["accrued_interest_excluding_overpayment"], Decimal("123.4567"))
        self.assertEqual(result["principal_due_excluding_overpayment"], Decimal("300000"))
        self.assertEqual(result["principal_excess"], Decimal("0"))

    def test_construct_flat_interest_amortisation_input(self):

        input_data = {
            "remaining_principal": Decimal("1.23456"),
            "original_principal": Decimal("0.12345"),
            "annual_interest_rate": Decimal("0.5567"),
            "total_term": 15,
            "remaining_term": 12,
            "precision": "2",
            "use_rule_of_78": False,
        }

        result = self.run_function(
            "construct_flat_interest_amortisation_input",
            vault_object=None,
            **input_data,
        )

        self.assertTrue(isinstance(result, tuple))

        self.assertEqual(result.remaining_principal, input_data["remaining_principal"])
        self.assertEqual(result.original_principal, input_data["original_principal"])
        self.assertEqual(
            result.annual_interest_rate,
            input_data["annual_interest_rate"],
        )
        self.assertEqual(result.precision, input_data["precision"])
        self.assertEqual(result.total_term, input_data["total_term"])
        self.assertEqual(result.remaining_term, input_data["remaining_term"])
        self.assertEqual(result.use_rule_of_78, input_data["use_rule_of_78"])

        self.assertEqual(len(result.__annotations__.keys()), 7)

    def test_get_flat_interest_amortised_loan_emi(self):
        test_cases = [
            {
                "description": "£1000, 1 year loan, no fee",
                "input": {
                    "original_principal": Decimal("1000"),
                    "total_interest": Decimal("12"),
                    "total_term": 12,
                    "precision": 2,
                },
                # (1000 + 12) / 12 rounded to 2 dp = 84.33
                "expected_result": Decimal("84.33"),
            }
        ]
        for test_case in test_cases:
            result = self.run_function(
                "_get_flat_interest_amortised_loan_emi",
                vault_object=None,
                **test_case["input"],
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_total_loan_interest(self):
        test_cases = [
            {
                "description": "£1000, 1 year loan",
                "input": {
                    "original_principal": Decimal("1000"),
                    "annual_interest_rate": Decimal("0.135"),
                    "total_term": 12,
                    "precision": 2,
                },
                "expected_result": Decimal("135.00"),
            }
        ]
        for test_case in test_cases:
            mock_vault = self.create_mock()
            result = self.run_function(
                "_get_total_loan_interest",
                mock_vault,
                **test_case["input"],
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_get_sum_to_total_term(self):
        test_cases = [
            {
                "description": "1 year loan",
                "term": 12,
                "expected_result": 78,
            },
            {
                "description": "2 year loan",
                "term": 24,
                "expected_result": 300,
            },
            {
                "description": "5 year loan",
                "term": 60,
                "expected_result": 1830,
            },
        ]
        for test_case in test_cases:
            result = self.run_function(
                "_get_sum_to_total_term", vault_object=None, term=test_case["term"]
            )
            self.assertEqual(result, test_case["expected_result"], test_case["description"])

    def test_round_with_different_rounding_methods(self):
        input_data = [
            ("round_floor", ROUND_FLOOR, Decimal("15.45")),
            ("round half down", ROUND_HALF_DOWN, Decimal("15.46")),
            ("round half up", ROUND_HALF_UP, Decimal("15.46")),
        ]

        for test_name, rounding, expected_amount in input_data:
            result = self.run_function(
                function_name="_round_decimal",
                vault_object=None,
                amount=Decimal("15.456"),
                decimal_places=2,
                rounding=rounding,
            )
            self.assertEqual(result, expected_amount, test_name)

    def test_round_with_different_precision(self):
        input_data = [
            ("0 dp", 0, Decimal("15")),
            ("2 dp", 2, Decimal("15.46")),
            ("5 dp", 5, Decimal("15.45556")),
        ]

        for test_name, decimal_places, expected_amount in input_data:
            result = self.run_function(
                function_name="_round_decimal",
                vault_object=None,
                amount=Decimal("15.455555"),
                decimal_places=decimal_places,
                rounding=ROUND_HALF_UP,
            )
            self.assertEqual(result, expected_amount, test_name)
