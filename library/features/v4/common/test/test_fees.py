# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.common.fees as fees

# inception sdk
from inception_sdk.test_framework.contracts.unit.contracts_v4.common import FeatureTest
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_extension import (
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    CustomInstruction,
    Phase,
    Posting,
)
from inception_sdk.test_framework.contracts.unit.contracts_v4.contracts_api_sentinels import (
    SentinelPosting,
)


class FeePostingsTest(FeatureTest):
    common_args = dict(
        customer_account_id=sentinel.customer_account_id,
        customer_account_address=sentinel.customer_account_address,
        denomination=sentinel.denomination,
        internal_account=sentinel.internal_account,
    )

    def test_fee_postings_for_0_amount(self):
        self.assertListEqual(
            fees.fee_postings(amount=Decimal("0"), **self.common_args),
            [],
        )

    def test_fee_postings_for_negative_amount(self):
        self.assertListEqual(
            fees.fee_postings(amount=Decimal("-1"), **self.common_args),
            [],
        )

    def test_fee_posting(self):
        self.assertListEqual(
            fees.fee_postings(
                amount=Decimal("1"),
                **self.common_args,
            ),
            [
                Posting(
                    credit=True,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_address=DEFAULT_ADDRESS,
                    account_id=sentinel.internal_account,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_address=sentinel.customer_account_address,
                    account_id=sentinel.customer_account_id,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
        )

    def test_fee_posting_reversal(self):
        self.assertListEqual(
            fees.fee_postings(
                amount=Decimal("1"),
                reversal=True,
                **self.common_args,
            ),
            [
                Posting(
                    credit=True,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_address=sentinel.customer_account_address,
                    account_id=sentinel.customer_account_id,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_address=DEFAULT_ADDRESS,
                    account_id=sentinel.internal_account,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
        )


class FeeCustomInstructionTest(FeatureTest):
    common_args = dict(
        customer_account_id=sentinel.customer_account_id,
        denomination=sentinel.denomination,
        internal_account=sentinel.internal_account,
    )

    @patch.object(fees, "fee_postings")
    def test_fee_custom_instruction_defaulted_customer_address(self, mock_fee_postings: MagicMock):
        fee_postings = [SentinelPosting("fee_1")]
        mock_fee_postings.return_value = fee_postings
        self.assertListEqual(
            fees.fee_custom_instruction(
                amount=Decimal("1"),
                instruction_details={"test": "details"},
                **self.common_args,
            ),
            [
                CustomInstruction(
                    postings=fee_postings,  # type: ignore
                    instruction_details={"test": "details"},
                    override_all_restrictions=True,
                )
            ],
        )
        mock_fee_postings.assert_called_once_with(
            customer_account_id=sentinel.customer_account_id,
            customer_account_address=DEFAULT_ADDRESS,
            denomination=sentinel.denomination,
            amount=Decimal("1"),
            internal_account=sentinel.internal_account,
            reversal=False,
        )

    @patch.object(fees, "fee_postings")
    def test_fee_custom_instruction_custom_customer_address(self, mock_fee_postings: MagicMock):
        fee_postings = [SentinelPosting("fee_1")]
        mock_fee_postings.return_value = fee_postings
        self.assertListEqual(
            fees.fee_custom_instruction(
                amount=Decimal("1"),
                customer_account_address=sentinel.customer_address,
                instruction_details={"test": "details"},
                **self.common_args,
            ),
            [
                CustomInstruction(
                    postings=fee_postings,  # type: ignore
                    instruction_details={"test": "details"},
                    override_all_restrictions=True,
                )
            ],
        )
        mock_fee_postings.assert_called_once_with(
            customer_account_id=sentinel.customer_account_id,
            customer_account_address=sentinel.customer_address,
            denomination=sentinel.denomination,
            amount=Decimal("1"),
            internal_account=sentinel.internal_account,
            reversal=False,
        )

    @patch.object(fees, "fee_postings")
    def test_fee_custom_instruction_reversal(self, mock_fee_postings: MagicMock):
        fee_postings = [SentinelPosting("fee_1")]
        mock_fee_postings.return_value = fee_postings
        self.assertListEqual(
            fees.fee_custom_instruction(
                amount=Decimal("1"),
                customer_account_address=sentinel.customer_address,
                reversal=True,
                **self.common_args,
            ),
            [
                CustomInstruction(
                    postings=fee_postings,  # type: ignore
                    override_all_restrictions=True,
                )
            ],
        )
        mock_fee_postings.assert_called_once_with(
            customer_account_id=sentinel.customer_account_id,
            customer_account_address=sentinel.customer_address,
            denomination=sentinel.denomination,
            amount=Decimal("1"),
            internal_account=sentinel.internal_account,
            reversal=True,
        )

    @patch.object(fees, "fee_postings")
    def test_fee_custom_instruction_no_postings(self, mock_fee_postings: MagicMock):
        mock_fee_postings.return_value = []
        self.assertListEqual(
            fees.fee_custom_instruction(
                amount=Decimal("1"),
                instruction_details={"test": "details"},
                **self.common_args,
            ),
            [],
        )

    def test_fee_custom_instruction_0_amount(self):
        self.assertListEqual(
            fees.fee_custom_instruction(
                amount=Decimal("0"),
                instruction_details={"test": "details"},
                **self.common_args,
            ),
            [],
        )

    def test_fee_custom_instruction_negative_amount(self):
        self.assertListEqual(
            fees.fee_custom_instruction(
                amount=Decimal("-1"),
                instruction_details={"test": "details"},
                **self.common_args,
            ),
            [],
        )
