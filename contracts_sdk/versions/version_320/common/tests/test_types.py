from datetime import datetime
from decimal import Decimal

from ..types import (
    defaultAddress,
    defaultAsset,
    PostingInstruction,
    PostingInstructionType,
    PostingInstructionBatch,
    Phase,
    StringShape,
    Parameter,
    ClientTransaction,
    OptionalValue,
)
from ....version_310.common.tests.test_types import PublicCommonV310TypesTestCase
from .....utils.exceptions import InvalidSmartContractError, StrongTypingError
from .....utils.symbols import ContractParameterLevel, DEFAULT_ADDRESS, DEFAULT_ASSET


class PublicCommonV320TypesTestCase(PublicCommonV310TypesTestCase):
    TS_320 = datetime(year=2020, month=1, day=1)
    account_id_320 = "test_account_id"

    def test_posting_instruction_balances_not_implemented(self):
        pi = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="xx",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id=self.account_id_320,
            account_address=defaultAddress.fixed_value,
            amount=Decimal(10),
            asset=defaultAsset.fixed_value,
            credit=False,
            denomination="GBP",
        )
        with self.assertRaises(NotImplementedError):
            pi.balances()

    def test_posting_instruction_missing_kwargs(self):
        with self.assertRaises(StrongTypingError):
            PostingInstruction(id="101", account_id=self.account_id_320, amount=Decimal(10))

    def test_posting_instruction_advice_field(self):
        with self.assertRaises(StrongTypingError):
            PostingInstruction(
                id="100",
                type=PostingInstructionType.TRANSFER,
                client_transaction_id="xx",
                pics=[],
                custom_instruction_grouping_key="yy",
                account_id=self.account_id_320,
                account_address=defaultAddress.fixed_value,
                amount=Decimal(10),
                asset=defaultAsset.fixed_value,
                credit=False,
                denomination="GBP",
                advice="test",
            )

    def test_posting_instruction_override_all_restrictions(self):
        with self.assertRaises(StrongTypingError):
            PostingInstruction(
                id="100",
                type=PostingInstructionType.TRANSFER,
                client_transaction_id="xx",
                pics=[],
                custom_instruction_grouping_key="yy",
                account_id=self.account_id_320,
                account_address=defaultAddress.fixed_value,
                amount=Decimal(10),
                asset=defaultAsset.fixed_value,
                credit=False,
                denomination="GBP",
                override_all_restrictions="test",
            )

    def test_posting_instruction_batch_balances_not_implemented(self):
        posting_instruction_batch = PostingInstructionBatch(
            batch_id="batch_id",
            batch_details={},
            client_id="Visa",
            client_batch_id="international-payment",
            value_timestamp=self.TS_320,
            posting_instructions=[
                PostingInstruction(
                    custom_instruction_grouping_key="some_key",
                    client_transaction_id="the-main-payment-id",
                    pics=["INTERNATIONAL_PAYMENT"],
                    instruction_details={"TYPE": "PURCHASE"},
                    type=PostingInstructionType.CUSTOM_INSTRUCTION,
                    credit=True,
                    amount=Decimal(10),
                    denomination="GBP",
                    account_id=self.account_id_320,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
        )

        with self.assertRaises(NotImplementedError):
            posting_instruction_batch.balances()

    def test_parameter_cannot_use_optional_default_value(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            Parameter(
                name="overdraft_limit",
                level=ContractParameterLevel.TEMPLATE,
                description="Overdraft limit",
                shape=OptionalValue,
                default_value=OptionalValue(value=1),
            )
        self.assertIn(
            "Non optional shapes must have a non optional default value: overdraft_limit",
            str(ex.exception),
        )

    def test_derived_parameters_cannot_have_default_values(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            Parameter(
                name="overdraft_limit",
                level=ContractParameterLevel.INSTANCE,
                description="Overdraft limit",
                shape=StringShape,
                default_value="1",
                derived=True,
            )
        self.assertIn(
            "Derived Parameters cannot have a default value or update permissions: "
            "overdraft_limit",
            str(ex.exception),
        )

    def test_client_transaction(self):
        post_one = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="out",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id=self.account_id_320,
            account_address=defaultAddress.fixed_value,
            amount=Decimal(10),
            asset=defaultAsset.fixed_value,
            credit=False,
            denomination="GBP",
        )
        post_two = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="in",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id=self.account_id_320,
            account_address=defaultAddress.fixed_value,
            amount=Decimal(0.1),
            asset=defaultAsset.fixed_value,
            credit=True,
            denomination="GBP",
        )
        trans = ClientTransaction([post_one, post_two])
        self.assertEqual("Missing implementation", str(trans.start_time))

    def test_posting_instruction_advice_set(self):
        common_kwargs = {
            "advice": True,
            "id": "123",
            "client_transaction_id": "123",
            "pics": ["test"],
            "custom_instruction_grouping_key": "123",
            "account_id": "123",
            "account_address": "test",
            "asset": "test",
            "credit": True,
            "denomination": "GBP",
        }

        pi = PostingInstruction(type=PostingInstructionType.AUTHORISATION, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertTrue(pi.advice)

        pi = PostingInstruction(
            type=PostingInstructionType.AUTHORISATION_ADJUSTMENT, **common_kwargs
        )
        self.assertTrue(hasattr(pi, "advice"))
        self.assertTrue(pi.advice)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(
                type=PostingInstructionType.CUSTOM_INSTRUCTION,
                phase=Phase.COMMITTED,
                **common_kwargs,
            )

        pi = PostingInstruction(type=PostingInstructionType.HARD_SETTLEMENT, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertTrue(pi.advice)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(type=PostingInstructionType.RELEASE, **common_kwargs)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(type=PostingInstructionType.SETTLEMENT, final=False, **common_kwargs)

        with self.assertRaises(InvalidSmartContractError):
            PostingInstruction(type=PostingInstructionType.TRANSFER, **common_kwargs)

    def test_posting_instruction_advice_not_set(self):
        common_kwargs = {
            "id": "123",
            "client_transaction_id": "123",
            "pics": ["test"],
            "custom_instruction_grouping_key": "123",
            "account_id": "123",
            "account_address": "test",
            "asset": "test",
            "credit": True,
            "denomination": "GBP",
        }

        pi = PostingInstruction(type=PostingInstructionType.AUTHORISATION, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertFalse(pi.advice)

        pi = PostingInstruction(
            type=PostingInstructionType.AUTHORISATION_ADJUSTMENT, **common_kwargs
        )
        self.assertTrue(hasattr(pi, "advice"))
        self.assertFalse(pi.advice)

        pi = PostingInstruction(
            type=PostingInstructionType.CUSTOM_INSTRUCTION, phase=Phase.COMMITTED, **common_kwargs
        )
        self.assertFalse(hasattr(pi, "advice"))

        pi = PostingInstruction(type=PostingInstructionType.HARD_SETTLEMENT, **common_kwargs)
        self.assertTrue(hasattr(pi, "advice"))
        self.assertFalse(pi.advice)

        pi = PostingInstruction(type=PostingInstructionType.RELEASE, **common_kwargs)
        self.assertFalse(hasattr(pi, "advice"))

        pi = PostingInstruction(
            type=PostingInstructionType.SETTLEMENT, final=False, **common_kwargs
        )
        self.assertFalse(hasattr(pi, "advice"))

        pi = PostingInstruction(type=PostingInstructionType.TRANSFER, **common_kwargs)
        self.assertFalse(hasattr(pi, "advice"))

    def test_posting_instruction_batch_validation_is_skipped_if_from_proto(self):
        # This instantiation should not raise an error even though the arguments are
        # invalid, as _from_proto is set to True
        try:
            PostingInstructionBatch(
                batch_id=123,  # Invalid type, str expected
                batch_details={},
                client_id="client_id",
                client_batch_id="client_batch_id",
                value_timestamp=self.TS_300,
                posting_instructions=[
                    PostingInstruction(
                        id="123",
                        type=PostingInstructionType.AUTHORISATION,
                        client_transaction_id="123",
                        instruction_details={"test": "testy"},
                        pics=["test"],
                        custom_instruction_grouping_key="123",
                        account_id="123",
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        credit=True,
                        denomination="GBP",
                    )
                ],
                _from_proto=True,  # Bypass validation
            )
        except Exception:
            self.fail("Creating PIB with _from_proto=True should not trigger type checks")
