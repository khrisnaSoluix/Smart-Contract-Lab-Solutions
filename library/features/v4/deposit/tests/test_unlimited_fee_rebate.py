# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, call, patch, sentinel

# features
import library.features.v4.deposit.unlimited_fee_rebate as unlimited_fee_rebate
from library.features.v4.common.test.mocks import mock_utils_get_parameter

# contracts api
from contracts_api import Posting as _Posting, Tside

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import (
    DEFAULT_DATETIME,
    FeatureTest,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    CustomInstruction,
    Phase,
    Posting,
)


class GroupPostingsByFeeEligibilityTest(FeatureTest):
    maxDiff = None

    def setUp(self) -> None:
        self.fee_rebate_internal_accounts = {
            sentinel.fee_1: sentinel.internal_account_1,
            sentinel.fee_2: sentinel.internal_account_2,
        }
        self.fee_rebate_types = [sentinel.fee_1, sentinel.fee_2]
        # get parameter
        patch_get_parameter = patch.object(unlimited_fee_rebate.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "fee_types_eligible_for_rebate": self.fee_rebate_types,
                "fee_rebate_internal_accounts": self.fee_rebate_internal_accounts,
                "denomination": sentinel.default_denomination,
            }
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    def test_group_posting_instructions_by_fee_eligibility_no_fee_postings(self):
        outbound_hard_settlement = MagicMock(instruction_details={})
        proposed_postings = [outbound_hard_settlement]

        result = unlimited_fee_rebate.group_posting_instructions_by_fee_eligibility(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            proposed_posting_instructions=proposed_postings,  # type: ignore
            denomination=sentinel.default_denomination,
        )

        expected_result = {
            "non_fee_postings": [outbound_hard_settlement],
            "fees_eligible_for_rebate": [],
            "fees_ineligible_for_rebate": [],
        }

        self.assertDictEqual(result, expected_result)
        self.mock_get_parameter.assert_not_called()

    @patch.object(unlimited_fee_rebate, "is_posting_instruction_eligible_for_fee_rebate")
    def test_group_posting_instructions_by_fee_eligibility_fee_postings_denomination_provided(
        self, mock_is_posting_instruction_eligible_for_fee_rebate: MagicMock
    ):
        mock_is_posting_instruction_eligible_for_fee_rebate.side_effect = [True, False, True]
        posting_instruction_1 = MagicMock(instruction_details={})
        posting_instruction_2 = MagicMock(instruction_details={"fee_type": sentinel.fee_1})
        posting_instruction_3 = MagicMock(instruction_details={"fee_type": sentinel.fee_3})
        posting_instruction_4 = MagicMock(instruction_details={"fee_type": sentinel.fee_2})

        proposed_postings = [
            posting_instruction_1,
            posting_instruction_2,
            posting_instruction_3,
            posting_instruction_4,
        ]

        result = unlimited_fee_rebate.group_posting_instructions_by_fee_eligibility(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            proposed_posting_instructions=proposed_postings,  # type: ignore
            denomination=sentinel.denomination,
        )

        expected_result = {
            "non_fee_postings": [posting_instruction_1],
            "fees_eligible_for_rebate": [posting_instruction_2, posting_instruction_4],
            "fees_ineligible_for_rebate": [posting_instruction_3],
        }

        self.assertDictEqual(result, expected_result)
        self.mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.vault,
                    name="fee_types_eligible_for_rebate",
                    at_datetime=DEFAULT_DATETIME,
                    is_json=True,
                ),
                call(
                    vault=sentinel.vault,
                    name="fee_rebate_internal_accounts",
                    at_datetime=DEFAULT_DATETIME,
                    is_json=True,
                ),
            ]
        )
        mock_is_posting_instruction_eligible_for_fee_rebate.assert_has_calls(
            calls=[
                call(
                    posting_instruction=posting_instruction_2,
                    eligible_fee_types=self.fee_rebate_types,
                    fee_rebate_internal_accounts=self.fee_rebate_internal_accounts,
                    denomination=sentinel.denomination,
                ),
                call(
                    posting_instruction=posting_instruction_3,
                    eligible_fee_types=self.fee_rebate_types,
                    fee_rebate_internal_accounts=self.fee_rebate_internal_accounts,
                    denomination=sentinel.denomination,
                ),
                call(
                    posting_instruction=posting_instruction_4,
                    eligible_fee_types=self.fee_rebate_types,
                    fee_rebate_internal_accounts=self.fee_rebate_internal_accounts,
                    denomination=sentinel.denomination,
                ),
            ]
        )

    @patch.object(unlimited_fee_rebate, "is_posting_instruction_eligible_for_fee_rebate")
    def test_group_posting_instructions_by_fee_eligibility_fee_postings_defaulted_denomination(
        self, mock_is_posting_instruction_eligible_for_fee_rebate: MagicMock
    ):
        mock_is_posting_instruction_eligible_for_fee_rebate.side_effect = [True, False, True]
        posting_instruction_1 = MagicMock(instruction_details={})
        posting_instruction_2 = MagicMock(instruction_details={"fee_type": sentinel.fee_1})
        posting_instruction_3 = MagicMock(instruction_details={"fee_type": sentinel.fee_3})
        posting_instruction_4 = MagicMock(instruction_details={"fee_type": sentinel.fee_2})

        proposed_postings = [
            posting_instruction_1,
            posting_instruction_2,
            posting_instruction_3,
            posting_instruction_4,
        ]

        result = unlimited_fee_rebate.group_posting_instructions_by_fee_eligibility(
            vault=sentinel.vault,
            effective_datetime=DEFAULT_DATETIME,
            proposed_posting_instructions=proposed_postings,  # type: ignore
        )

        expected_result = {
            "non_fee_postings": [posting_instruction_1],
            "fees_eligible_for_rebate": [posting_instruction_2, posting_instruction_4],
            "fees_ineligible_for_rebate": [posting_instruction_3],
        }

        self.assertDictEqual(result, expected_result)
        self.mock_get_parameter.assert_has_calls(
            calls=[
                call(
                    vault=sentinel.vault,
                    name="fee_types_eligible_for_rebate",
                    at_datetime=DEFAULT_DATETIME,
                    is_json=True,
                ),
                call(
                    vault=sentinel.vault,
                    name="fee_rebate_internal_accounts",
                    at_datetime=DEFAULT_DATETIME,
                    is_json=True,
                ),
            ]
        )
        mock_is_posting_instruction_eligible_for_fee_rebate.assert_has_calls(
            calls=[
                call(
                    posting_instruction=posting_instruction_2,
                    eligible_fee_types=self.fee_rebate_types,
                    fee_rebate_internal_accounts=self.fee_rebate_internal_accounts,
                    denomination=sentinel.default_denomination,
                ),
                call(
                    posting_instruction=posting_instruction_3,
                    eligible_fee_types=self.fee_rebate_types,
                    fee_rebate_internal_accounts=self.fee_rebate_internal_accounts,
                    denomination=sentinel.default_denomination,
                ),
                call(
                    posting_instruction=posting_instruction_4,
                    eligible_fee_types=self.fee_rebate_types,
                    fee_rebate_internal_accounts=self.fee_rebate_internal_accounts,
                    denomination=sentinel.default_denomination,
                ),
            ]
        )


class RebateFeesTest(FeatureTest):
    tside = Tside.LIABILITY

    def setUp(self) -> None:
        self.fee_rebate_internal_accounts = {
            sentinel.fee_1: sentinel.internal_account_1,
            sentinel.fee_2: sentinel.internal_account_2,
        }
        self.posting_instruction_1 = self.outbound_hard_settlement(
            amount=Decimal("1"),
            instruction_details={"fee_type": sentinel.fee_1},
            _own_account_id=sentinel.account_id,
        )
        self.posting_instruction_2 = self.outbound_hard_settlement(
            amount=Decimal("1"),
            instruction_details={"fee_type": sentinel.fee_2},
            _own_account_id=sentinel.account_id,
        )
        self.grouped_posting_instructions = {
            unlimited_fee_rebate.NON_FEE_POSTINGS: [sentinel.non_fee_postings],
            unlimited_fee_rebate.FEES_ELIGIBLE_FOR_REBATE: [
                self.posting_instruction_1,
                self.posting_instruction_2,
            ],
            unlimited_fee_rebate.FEES_INELIGIBLE_FOR_REBATE: [sentinel.non_eligible_fee_postings],
        }
        # get parameter
        patch_get_parameter = patch.object(unlimited_fee_rebate.utils, "get_parameter")
        self.mock_get_parameter = patch_get_parameter.start()
        self.mock_get_parameter.side_effect = mock_utils_get_parameter(
            parameters={
                "fee_rebate_internal_accounts": self.fee_rebate_internal_accounts,
                "denomination": sentinel.default_denomination,
            }
        )
        patch_group_posting_instructions_by_fee_eligibility = patch.object(
            unlimited_fee_rebate, "group_posting_instructions_by_fee_eligibility"
        )
        self.mock_group_posting_instructions_by_fee_eligibility = (
            patch_group_posting_instructions_by_fee_eligibility.start()
        )
        self.mock_group_posting_instructions_by_fee_eligibility.return_value = (
            self.grouped_posting_instructions
        )

        self.addCleanup(patch.stopall)
        return super().setUp()

    @patch.object(unlimited_fee_rebate.utils, "balance_at_coordinates")
    def test_rebate_fees_with_eligible_fee_postings_default_denomination(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.return_value = Decimal("-1")

        expected_result = [
            CustomInstruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("1"),
                        denomination=sentinel.default_denomination,
                        account_id=sentinel.account_id,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("1"),
                        denomination=sentinel.default_denomination,
                        account_id=sentinel.internal_account_1,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ],
                instruction_details={
                    "description": "Rebate charged fee, sentinel.fee_1",
                    "gl_impacted": "True",
                },
                override_all_restrictions=True,
            ),
            CustomInstruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("1"),
                        denomination=sentinel.default_denomination,
                        account_id=sentinel.account_id,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("1"),
                        denomination=sentinel.default_denomination,
                        account_id=sentinel.internal_account_2,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ],
                instruction_details={
                    "description": "Rebate charged fee, sentinel.fee_2",
                    "gl_impacted": "True",
                },
                override_all_restrictions=True,
            ),
        ]

        self.assertListEqual(
            unlimited_fee_rebate.rebate_fees(
                vault=MagicMock(account_id=sentinel.account_id),
                effective_datetime=DEFAULT_DATETIME,
                posting_instructions=sentinel.posting_instructions,
            ),
            expected_result,
        )

    @patch.object(unlimited_fee_rebate.utils, "balance_at_coordinates")
    def test_rebate_fees_with_eligible_fee_postings_provided_denomination(
        self, mock_balance_at_coordinates: MagicMock
    ):
        mock_balance_at_coordinates.return_value = Decimal("-1")

        expected_result = [
            CustomInstruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("1"),
                        denomination=sentinel.denomination,
                        account_id=sentinel.account_id,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("1"),
                        denomination=sentinel.denomination,
                        account_id=sentinel.internal_account_1,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ],
                instruction_details={
                    "description": "Rebate charged fee, sentinel.fee_1",
                    "gl_impacted": "True",
                },
                override_all_restrictions=True,
            ),
            CustomInstruction(
                postings=[
                    Posting(
                        credit=True,
                        amount=Decimal("1"),
                        denomination=sentinel.denomination,
                        account_id=sentinel.account_id,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    Posting(
                        credit=False,
                        amount=Decimal("1"),
                        denomination=sentinel.denomination,
                        account_id=sentinel.internal_account_2,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ],
                instruction_details={
                    "description": "Rebate charged fee, sentinel.fee_2",
                    "gl_impacted": "True",
                },
                override_all_restrictions=True,
            ),
        ]

        self.assertListEqual(
            unlimited_fee_rebate.rebate_fees(
                vault=MagicMock(account_id=sentinel.account_id),
                effective_datetime=DEFAULT_DATETIME,
                posting_instructions=sentinel.posting_instructions,
                denomination=sentinel.denomination,
            ),
            expected_result,
        )

    def test_rebate_fees_no_fee_postings(self):
        grouped_posting_instructions = (
            self.mock_group_posting_instructions_by_fee_eligibility.return_value
        )
        grouped_posting_instructions[unlimited_fee_rebate.FEES_ELIGIBLE_FOR_REBATE] = []
        self.mock_group_posting_instructions_by_fee_eligibility.return_value = (
            grouped_posting_instructions
        )
        self.assertListEqual(
            unlimited_fee_rebate.rebate_fees(
                vault=sentinel.vault,
                effective_datetime=DEFAULT_DATETIME,
                posting_instructions=sentinel.posting_instructions,
            ),
            [],
        )


@patch.object(unlimited_fee_rebate.utils, "get_current_debit_balance")
class IsPostingEligibleForRebateTest(FeatureTest):
    tside = Tside.LIABILITY

    def test_is_posting_instruction_eligible_for_fee_rebate_non_eligible_posting_type(
        self, mock_get_current_debit_balance: MagicMock
    ):
        mock_posting_instruction = MagicMock()
        type(mock_posting_instruction).type = PropertyMock(
            return_value="ineligible_posting_instruction_type"
        )
        result = unlimited_fee_rebate.is_posting_instruction_eligible_for_fee_rebate(
            posting_instruction=mock_posting_instruction,
            eligible_fee_types=sentinel.eligible_fee_types,
            fee_rebate_internal_accounts=sentinel.fee_rebate_internal_accounts,
            denomination=sentinel.denomination,
        )
        self.assertFalse(result)
        mock_get_current_debit_balance.assert_not_called()

    def test_is_posting_instruction_eligible_for_fee_rebate_positive_posting_balance(
        self, mock_get_current_debit_balance: MagicMock
    ):
        mock_get_current_debit_balance.return_value = Decimal("10")
        result = unlimited_fee_rebate.is_posting_instruction_eligible_for_fee_rebate(
            posting_instruction=self.inbound_transfer(amount=Decimal("10")),
            eligible_fee_types=sentinel.eligible_fee_types,
            fee_rebate_internal_accounts=sentinel.fee_rebate_internal_accounts,
            denomination=sentinel.denomination,
        )
        self.assertFalse(result)

    def test_is_posting_instruction_eligible_for_fee_rebate_credit_custom_instruction(
        self, mock_get_current_debit_balance: MagicMock
    ):
        mock_get_current_debit_balance.return_value = Decimal("0")
        result = unlimited_fee_rebate.is_posting_instruction_eligible_for_fee_rebate(
            posting_instruction=self.custom_instruction(
                postings=[
                    _Posting(
                        credit=True,
                        amount=Decimal("10"),
                        denomination=sentinel.denomination,
                        account_id=sentinel.account_id,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                    _Posting(
                        credit=False,
                        amount=Decimal("10"),
                        denomination=sentinel.denomination,
                        account_id=sentinel.account_id_2,
                        account_address="ANOTHER_ADDRESS",
                        asset=DEFAULT_ASSET,
                        phase=Phase.COMMITTED,
                    ),
                ],
                own_account_id=sentinel.account_id,
            ),
            eligible_fee_types=sentinel.eligible_fee_types,
            fee_rebate_internal_accounts=sentinel.fee_rebate_internal_accounts,
            denomination=sentinel.denomination,
        )
        self.assertFalse(result)

    def test_is_posting_instruction_eligible_for_fee_rebate_no_fee_metadata(
        self, mock_get_current_debit_balance: MagicMock
    ):
        mock_get_current_debit_balance.return_value = Decimal("10")
        result = unlimited_fee_rebate.is_posting_instruction_eligible_for_fee_rebate(
            posting_instruction=self.outbound_hard_settlement(
                amount=Decimal("10"), _own_account_id=sentinel.account_id
            ),
            eligible_fee_types=sentinel.eligible_fee_types,
            fee_rebate_internal_accounts=sentinel.fee_rebate_internal_accounts,
            denomination=sentinel.denomination,
        )
        self.assertFalse(result)

    def test_is_posting_instruction_eligible_for_fee_rebate_fee_metadata_not_in_eligible_fee_types(
        self, mock_get_current_debit_balance: MagicMock
    ):
        mock_get_current_debit_balance.return_value = Decimal("10")
        result = unlimited_fee_rebate.is_posting_instruction_eligible_for_fee_rebate(
            posting_instruction=self.outbound_hard_settlement(
                amount=Decimal("10"),
                instruction_details={"fee_type": sentinel.fee_type_2},
                _own_account_id=sentinel.account_id,
            ),
            eligible_fee_types=[sentinel.fee_type_1],
            fee_rebate_internal_accounts=sentinel.fee_rebate_internal_accounts,
            denomination=sentinel.denomination,
        )
        self.assertFalse(result)

    def test_is_posting_instruction_eligible_for_fee_rebate_fee_type_internal_account_not_present(
        self, mock_get_current_debit_balance: MagicMock
    ):
        mock_get_current_debit_balance.return_value = Decimal("10")
        result = unlimited_fee_rebate.is_posting_instruction_eligible_for_fee_rebate(
            posting_instruction=self.outbound_hard_settlement(
                amount=Decimal("10"),
                instruction_details={"fee_type": sentinel.fee_type_2},
                _own_account_id=sentinel.account_id,
            ),
            eligible_fee_types=[sentinel.fee_type_2],
            fee_rebate_internal_accounts={sentinel.fee_type_1: sentinel.internal_account_1},
            denomination=sentinel.denomination,
        )
        self.assertFalse(result)

    def test_is_posting_instruction_eligible_for_fee_rebate_is_eligible(
        self, mock_get_current_debit_balance: MagicMock
    ):
        mock_get_current_debit_balance.return_value = Decimal("10")
        result = unlimited_fee_rebate.is_posting_instruction_eligible_for_fee_rebate(
            posting_instruction=self.outbound_hard_settlement(
                amount=Decimal("10"),
                instruction_details={"fee_type": sentinel.fee_type_1},
                _own_account_id=sentinel.account_id,
            ),
            eligible_fee_types=[sentinel.fee_type_1],
            fee_rebate_internal_accounts={sentinel.fee_type_1: sentinel.internal_account_1},
            denomination=sentinel.denomination,
        )
        self.assertTrue(result)
