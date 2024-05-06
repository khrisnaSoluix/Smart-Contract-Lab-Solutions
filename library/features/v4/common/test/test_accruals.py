# standard libs
from decimal import Decimal
from unittest.mock import MagicMock, patch, sentinel

# features
import library.features.v4.common.accruals as accruals

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


class AccrualsTestCommon(FeatureTest):
    maxDiff = None


class AccrualPostingsTest(AccrualsTestCommon):
    common_args = dict(
        customer_account=sentinel.customer_account,
        denomination=sentinel.denomination,
        customer_address=sentinel.customer_address,
        internal_account=sentinel.internal_account,
    )

    def test_accrual_postings_for_0_amount(self):
        self.assertListEqual(
            accruals.accrual_postings(amount=Decimal("0"), payable=True, **self.common_args),
            [],
        )

    def test_accrual_postings_for_negative_amount(self):
        self.assertListEqual(
            accruals.accrual_postings(amount=Decimal("-1"), payable=True, **self.common_args),
            [],
        )

    def test_accrual_postings_for_payable_non_reversal(self):
        self.assertListEqual(
            accruals.accrual_postings(
                amount=Decimal("1"),
                payable=True,
                reversal=False,
                **self.common_args,
            ),
            [
                Posting(
                    credit=True,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_address=sentinel.customer_address,
                    account_id=sentinel.customer_account,
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

    def test_accrual_postings_for_payable_reversal(self):
        self.assertListEqual(
            accruals.accrual_postings(
                amount=Decimal("1"),
                payable=True,
                reversal=True,
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
                    account_address=sentinel.customer_address,
                    account_id=sentinel.customer_account,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
        )

    def test_accrual_postings_for_receivable_non_reversal(self):
        self.assertListEqual(
            accruals.accrual_postings(
                amount=Decimal("1"),
                payable=False,
                reversal=False,
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
                    account_address=sentinel.customer_address,
                    account_id=sentinel.customer_account,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
        )

    def test_accrual_postings_for_receivable_reversal(self):
        self.assertListEqual(
            accruals.accrual_postings(
                amount=Decimal("1"),
                payable=False,
                reversal=True,
                **self.common_args,
            ),
            [
                Posting(
                    credit=True,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_address=sentinel.customer_address,
                    account_id=sentinel.customer_account,
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


class AccrualCustomInstructionTest(AccrualsTestCommon):
    common_args = dict(
        customer_account=sentinel.customer_account,
        denomination=sentinel.denomination,
        customer_address=sentinel.customer_address,
        internal_account=sentinel.internal_account,
    )

    @patch.object(accruals, "accrual_postings")
    def test_accrual_custom_instruction(self, mock_accrual_postings: MagicMock):
        accrual_postings = [SentinelPosting("accrual_1")]
        mock_accrual_postings.return_value = accrual_postings
        self.assertListEqual(
            accruals.accrual_custom_instruction(
                amount=Decimal("1"),
                instruction_details={"test": "details"},
                payable=sentinel.payable,
                **self.common_args,
            ),
            [
                CustomInstruction(
                    postings=accrual_postings,
                    instruction_details={"test": "details"},
                    override_all_restrictions=True,
                )
            ],
        )
        mock_accrual_postings.assert_called_once_with(
            customer_account=sentinel.customer_account,
            customer_address=sentinel.customer_address,
            denomination=sentinel.denomination,
            amount=Decimal("1"),
            internal_account=sentinel.internal_account,
            payable=sentinel.payable,
            reversal=False,
        )

    @patch.object(accruals, "accrual_postings")
    def test_accrual_custom_instruction_no_postings(self, mock_accrual_postings: MagicMock):
        mock_accrual_postings.return_value = []
        self.assertListEqual(
            accruals.accrual_custom_instruction(
                amount=Decimal("1"),
                instruction_details={"test": "details"},
                payable=sentinel.payable,
                **self.common_args,
            ),
            [],
        )

    def test_accrual_custom_instruction_0_amount(self):
        self.assertListEqual(
            accruals.accrual_custom_instruction(
                amount=Decimal("0"),
                instruction_details={"test": "details"},
                payable=True,
                **self.common_args,
            ),
            [],
        )

    def test_accrual_custom_instruction_negative_amount(self):
        self.assertListEqual(
            accruals.accrual_custom_instruction(
                amount=Decimal("-1"),
                instruction_details={"test": "details"},
                payable=True,
                **self.common_args,
            ),
            [],
        )


class AccrualApplicationPostingsTest(AccrualsTestCommon):
    common_args = dict(
        customer_account=sentinel.customer_account,
        denomination=sentinel.denomination,
        accrual_customer_address=sentinel.accrual_customer_address,
        accrual_internal_account=sentinel.accrual_internal_account,
        application_internal_account=sentinel.application_internal_account,
        application_customer_address=sentinel.application_customer_address,
    )

    def test_accrual_application_postings_for_0_amount(self):
        self.assertListEqual(
            accruals.accrual_application_postings(
                application_amount=Decimal("0"),
                accrual_amount=sentinel.accrual_amount,
                payable=True,
                **self.common_args,
            ),
            [],
        )

    def test_accrual_application_postings_for_negative_amount(self):
        self.assertListEqual(
            accruals.accrual_application_postings(
                application_amount=Decimal("-1"),
                accrual_amount=sentinel.accrual_amount,
                payable=True,
                **self.common_args,
            ),
            [],
        )

    @patch.object(accruals, "accrual_postings")
    def test_accrual_application_postings_for_payable_application(
        self, mock_accrual_postings: MagicMock
    ):
        mock_accrual_postings.return_value = [sentinel.accrual_postings]
        postings = accruals.accrual_application_postings(
            application_amount=Decimal("1"),
            accrual_amount=sentinel.accrual_amount,
            payable=True,
            **self.common_args,
        )
        self.assertListEqual(
            postings,
            [
                Posting(
                    credit=True,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_address=sentinel.application_customer_address,
                    account_id=sentinel.customer_account,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_address=DEFAULT_ADDRESS,
                    account_id=sentinel.application_internal_account,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                sentinel.accrual_postings,
            ],
        )

        mock_accrual_postings.assert_called_once_with(
            customer_account=sentinel.customer_account,
            customer_address=sentinel.accrual_customer_address,
            denomination=sentinel.denomination,
            amount=sentinel.accrual_amount,
            internal_account=sentinel.accrual_internal_account,
            payable=True,
            reversal=True,
        )

    @patch.object(accruals, "accrual_postings")
    def test_accrual_application_postings_for_receivable_application(
        self, mock_accrual_postings: MagicMock
    ):
        mock_accrual_postings.return_value = [sentinel.accrual_postings]
        postings = accruals.accrual_application_postings(
            application_amount=Decimal("1"),
            accrual_amount=sentinel.accrual_amount,
            payable=False,
            **self.common_args,
        )
        self.assertListEqual(
            postings,
            [
                Posting(
                    credit=True,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_address=DEFAULT_ADDRESS,
                    account_id=sentinel.application_internal_account,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    credit=False,
                    amount=Decimal("1"),
                    denomination=sentinel.denomination,
                    account_address=sentinel.application_customer_address,
                    account_id=sentinel.customer_account,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                sentinel.accrual_postings,
            ],
        )

        mock_accrual_postings.assert_called_once_with(
            customer_account=sentinel.customer_account,
            customer_address=sentinel.accrual_customer_address,
            denomination=sentinel.denomination,
            amount=sentinel.accrual_amount,
            internal_account=sentinel.accrual_internal_account,
            payable=False,
            reversal=True,
        )


class AccrualApplicationCustomInstructionTest(AccrualsTestCommon):
    common_args = dict(
        customer_account=sentinel.customer_account,
        denomination=sentinel.denomination,
        accrual_customer_address=sentinel.accrual_customer_address,
        accrual_internal_account=sentinel.accrual_internal_account,
        application_internal_account=sentinel.application_internal_account,
        application_customer_address=sentinel.application_customer_address,
    )

    @patch.object(accruals, "accrual_application_postings")
    def test_accrual_application_custom_instruction(self, mock_application_postings: MagicMock):
        application_postings = [SentinelPosting("application_1")]

        mock_application_postings.return_value = application_postings
        self.assertEqual(
            accruals.accrual_application_custom_instruction(
                customer_account=sentinel.customer_account,
                denomination=sentinel.denomination,
                application_amount=Decimal("1"),
                accrual_amount=Decimal("1"),
                instruction_details={"test": "details"},
                accrual_customer_address=sentinel.accrual_customer_address,
                application_customer_address=sentinel.accrual_customer_address,
                accrual_internal_account=sentinel.accrual_internal_account,
                application_internal_account=sentinel.application_internal_account,
                payable=sentinel.payable,
            ),
            [
                CustomInstruction(
                    postings=application_postings,
                    instruction_details={"test": "details"},
                    override_all_restrictions=True,
                )
            ],
        )

        mock_application_postings.assert_called_once_with(
            customer_account=sentinel.customer_account,
            denomination=sentinel.denomination,
            application_amount=Decimal("1"),
            accrual_amount=Decimal("1"),
            accrual_customer_address=sentinel.accrual_customer_address,
            application_customer_address=sentinel.accrual_customer_address,
            accrual_internal_account=sentinel.accrual_internal_account,
            application_internal_account=sentinel.application_internal_account,
            payable=sentinel.payable,
        )

    @patch.object(accruals, "accrual_application_postings")
    def test_accrual_application_custom_instruction_no_postings(
        self, mock_application_postings: MagicMock
    ):

        mock_application_postings.return_value = []
        self.assertListEqual(
            accruals.accrual_application_custom_instruction(
                customer_account=sentinel.customer_account,
                denomination=sentinel.denomination,
                application_amount=Decimal("1"),
                accrual_amount=Decimal("1"),
                instruction_details={"test": "details"},
                accrual_customer_address=sentinel.accrual_customer_address,
                application_customer_address=sentinel.accrual_customer_address,
                accrual_internal_account=sentinel.accrual_internal_account,
                application_internal_account=sentinel.application_internal_account,
                payable=sentinel.payable,
            ),
            [],
        )

    def test_accrual_application_custom_instruction_zero_amount(self):
        self.assertListEqual(
            accruals.accrual_application_custom_instruction(
                customer_account=sentinel.customer_account,
                denomination=sentinel.denomination,
                application_amount=Decimal("0"),
                accrual_amount=Decimal("0"),
                instruction_details={"test": "details"},
                accrual_customer_address=sentinel.accrual_customer_address,
                application_customer_address=sentinel.accrual_customer_address,
                accrual_internal_account=sentinel.accrual_internal_account,
                application_internal_account=sentinel.application_internal_account,
                payable=True,
            ),
            [],
        )

    def test_accrual_application_custom_instruction_negative_amount(self):
        self.assertListEqual(
            accruals.accrual_application_custom_instruction(
                customer_account=sentinel.customer_account,
                denomination=sentinel.denomination,
                application_amount=Decimal("-1"),
                accrual_amount=Decimal("-1"),
                instruction_details={"test": "details"},
                accrual_customer_address=sentinel.accrual_customer_address,
                application_customer_address=sentinel.accrual_customer_address,
                accrual_internal_account=sentinel.accrual_internal_account,
                application_internal_account=sentinel.application_internal_account,
                payable=True,
            ),
            [],
        )
