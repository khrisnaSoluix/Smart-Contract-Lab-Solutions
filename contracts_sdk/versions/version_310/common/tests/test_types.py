from datetime import datetime
from decimal import Decimal

from ..types import (
    AccountIdShape,
    AddressDetails,
    ClientTransaction,
    DateShape,
    defaultAddress,
    defaultAsset,
    DenominationShape,
    Level,
    NumberShape,
    OptionalShape,
    OptionalValue,
    Parameter,
    PostingInstruction,
    PostingInstructionType,
    StringShape,
    PostingInstructionBatch,
    Phase,
)
from ....version_300.common.tests.test_types import PublicCommonV300TypesTestCase
from .....utils.exceptions import InvalidSmartContractError, StrongTypingError
from .....utils.symbols import DEFAULT_ADDRESS, DEFAULT_ASSET


class PublicCommonV310TypesTestCase(PublicCommonV300TypesTestCase):
    TS_310 = datetime(year=2020, month=1, day=1)
    account_id_310 = "test_account_id"

    def test_posting_instruction_balances_not_implemented(self):
        pi = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="xx",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id=self.account_id_310,
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
            PostingInstruction(id="101", account_id=self.account_id_310, amount=Decimal(10))

    def test_account_id_shape(self):
        AccountIdShape.validate_value(value="1231234")

    def test_account_id_shape_invalid_type(self):
        with self.assertRaises(InvalidSmartContractError):
            AccountIdShape.validate_value(value=121231234)

    def test_address_details(self):
        default = AddressDetails(
            account_address="DEFAULT", description="Default address", tags=["default"]
        )
        other_default = AddressDetails(
            account_address="DEFAULT", description="Default address", tags=["default"]
        )
        self.assertEqual(default, other_default)

    def test_date_shape(self):
        DateShape.validate_value(value=datetime(2020, 3, 27))

    def test_date_shape_invalid_type(self):
        with self.assertRaises(InvalidSmartContractError):
            DateShape.validate_value(value="27/03/2020")

    def test_denomination_shape(self):
        DenominationShape.validate_value(value="GBP")

    def test_denomination_shape_invalid_type(self):
        with self.assertRaises(InvalidSmartContractError):
            DenominationShape.validate_value(value=1000)

    def test_optional_shape(self):
        optional_shape = OptionalShape(shape=StringShape)
        optional_shape.validate_value(value=OptionalValue(value="optional string value"))

    def test_optional_shape_invalid_type(self):
        with self.assertRaises(InvalidSmartContractError):
            OptionalShape.validate_value(value=27)

    def test_parameter(self):
        parameter = Parameter(
            name="day_of_month",
            description="Which day would you like interest to be paid?",
            display_name="Day of month to pay interest",
            level=Level.GLOBAL,
            default_value=27,
            derived=False,
            shape=NumberShape(min_value=1, max_value=28, step=1),
        )
        self.assertEqual(parameter.default_value, 27)

    def test_client_transaction(self):
        post_one = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="out",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id=self.account_id_310,
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
            account_id=self.account_id_310,
            account_address=defaultAddress.fixed_value,
            amount=Decimal(0.1),
            asset=defaultAsset.fixed_value,
            credit=True,
            denomination="GBP",
        )
        trans = ClientTransaction([post_one, post_two])
        self.assertEqual("Missing implementation", str(trans.start_time))

    def test_string_shape(self):
        StringShape.validate_value(value="valid string")

    def test_string_shape_invalid_value(self):
        with self.assertRaises(InvalidSmartContractError):
            StringShape.validate_value(value=278)

    def test_posting_instruction_batch_balances_not_implemented(self):
        posting_instruction_batch = PostingInstructionBatch(
            batch_id="batch_id",
            batch_details={},
            client_id="Visa",
            client_batch_id="international-payment",
            value_timestamp=self.TS_310,
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
                    account_id=self.account_id_310,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
        )

        with self.assertRaises(NotImplementedError):
            posting_instruction_batch.balances()
