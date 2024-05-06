from datetime import datetime
from decimal import Decimal

from ..types import (
    Balance,
    PostingInstruction,
    PostingInstructionType,
    defaultAddress,
    defaultAsset,
    NumberKind,
    Phase,
    Tside,
    Level,
    Features,
    NoteType,
    Rejected,
    RejectedReason,
    UpdatePermission,
    Parameter,
    NumberShape,
    StringShape,
    AccountIdShape,
    DenominationShape,
    DateShape,
    ClientTransaction,
    ClientTransactionEffects,
    ClientTransactionEffectsDefaultDict,
    BalanceDefaultDict,
    BalanceTimeseries,
    FlagTimeseries,
    ParameterTimeseries,
    PostingInstructionBatch,
)
from .....utils.symbols import DEFAULT_ADDRESS, DEFAULT_ASSET
from .....utils.exceptions import StrongTypingError


class PublicCommonV300TypesTestCase:
    TS_300 = datetime(year=2020, month=1, day=1)
    account_id_300 = "test_account_id"

    def test_balance_credit(self):
        balance = Balance(credit=Decimal(100))
        self.assertEqual(balance.credit, Decimal(100))
        self.assertEqual(balance.net, 0)
        self.assertEqual(balance.debit, 0)

    def test_balance_net(self):
        balance = Balance(net=Decimal(120))
        self.assertEqual(balance.credit, 0)
        self.assertEqual(balance.net, Decimal(120))
        self.assertEqual(balance.debit, 0)

    def test_balance_debit(self):
        balance = Balance(debit=Decimal(19.99))
        self.assertEqual(balance.credit, 0)
        self.assertEqual(balance.net, 0)
        self.assertEqual(balance.debit, Decimal(19.99))

    def test_balance_timeseries(self):
        key_out = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_OUT)
        key_in = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        balances = BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0), purchase),
                (datetime(2020, 1, 15, 12, 25, 0), refund),
            ]
        )
        self.assertEqual(balances.at(timestamp=datetime(2020, 1, 15, 11, 20, 0)), purchase)

    def test_balance_defaultdict_type_checking_on_init(self):
        key = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_OUT)
        with self.assertRaises(StrongTypingError):
            BalanceDefaultDict(mapping={key: "not_a_balance"})

    def test_balance_default_dict_default_factory_from_proto(self):
        balance_default_dict = BalanceDefaultDict(
            mapping={"wrong type": "not_a_balance"}, _from_proto=True
        )
        self.assertEqual(balance_default_dict["wrong type"], "not_a_balance")
        with self.assertRaises(StrongTypingError):
            balance_default_dict["another wrong type"]

    def test_balance_default_dict_default_factory_raises_when_using_wrong_type(self):
        balance_default_dict = BalanceDefaultDict()
        with self.assertRaises(StrongTypingError):
            balance_default_dict["wrong type"]

    def test_balance_default_dict_default_factory_happy_path(self):
        balance_default_dict = BalanceDefaultDict()
        valid_type_balance_key = (
            defaultAddress.fixed_value,
            defaultAsset.fixed_value,
            "GBP",
            Phase.PENDING_OUT,
        )
        self.assertEqual(balance_default_dict[valid_type_balance_key], Balance())

    def test_balance_defaultdict_bypass_type_checking_on_init(self):
        key = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_OUT)
        purchase = BalanceDefaultDict(mapping={key: "not_a_balance"}, _from_proto=True)
        self.assertEqual(purchase[key], "not_a_balance")

    def test_balance_timeseries_type_checking(self):
        key_out = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_OUT)
        key_in = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        not_a_balance = "not_a_balance"
        with self.assertRaises(StrongTypingError):
            BalanceTimeseries(
                [
                    (datetime(2020, 1, 15, 11, 19, 0), purchase),
                    (datetime(2020, 1, 15, 12, 25, 0), refund),
                    (datetime(2020, 1, 15, 12, 31, 0), not_a_balance),
                ]
            )

    def test_balance_timeseries_bypass_type_checking(self):
        key_out = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_OUT)
        key_in = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        not_a_balance = "not_a_balance"
        BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0), purchase),
                (datetime(2020, 1, 15, 12, 25, 0), refund),
                (datetime(2020, 1, 15, 12, 31, 0), not_a_balance),
            ],
            _from_proto=True,
        )

    def test_posting_instruction_balances_not_implemented(self):
        pi = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="xx",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id=self.account_id_300,
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
            PostingInstruction(id="101", account_id="1234512", amount=Decimal(10))

    def test_client_transaction(self):
        post_one = PostingInstruction(
            id="100",
            type=PostingInstructionType.TRANSFER,
            client_transaction_id="out",
            pics=[],
            custom_instruction_grouping_key="yy",
            account_id=self.account_id_300,
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
            account_id=self.account_id_300,
            account_address=defaultAddress.fixed_value,
            amount=Decimal(0.1),
            asset=defaultAsset.fixed_value,
            credit=True,
            denomination="GBP",
        )
        trans = ClientTransaction([post_one, post_two])
        self.assertEqual("Missing implementation", str(trans.start_time))

    def test_client_transaction_effect(self):
        effect = ClientTransactionEffects(settled=Decimal(1999))
        key = (defaultAddress.fixed_value, defaultAsset.fixed_value, "GBP")
        client_effect = ClientTransactionEffectsDefaultDict(mapping={key: effect})
        self.assertEqual(client_effect[key].settled, 1999)

    def test_client_transaction_effect_missing_denomination(self):
        effect = ClientTransactionEffects()
        with self.assertRaises(StrongTypingError):
            ClientTransactionEffectsDefaultDict(
                mapping={
                    (defaultAddress.fixed_value, defaultAsset.fixed_value): effect,
                }
            )

    def test_posting_instrucion_type_enum(self):
        self.assertEqual(PostingInstructionType.AUTHORISATION, "Authorisation")
        self.assertEqual(PostingInstructionType.AUTHORISATION_ADJUSTMENT, "AuthorisationAdjustment")
        self.assertEqual(PostingInstructionType.CUSTOM_INSTRUCTION, "CustomInstruction")
        self.assertEqual(PostingInstructionType.HARD_SETTLEMENT, "HardSettlement")
        self.assertEqual(PostingInstructionType.RELEASE, "Release")
        self.assertEqual(PostingInstructionType.SETTLEMENT, "Settlement")
        self.assertEqual(PostingInstructionType.TRANSFER, "Transfer")

    def test_phase_enum(self):
        self.assertEqual(Phase.PENDING_IN, "pending_in")
        self.assertEqual(Phase.PENDING_OUT, "pending_out")
        self.assertEqual(Phase.COMMITTED, "committed")

    def test_number_kind_enum(self):
        self.assertEqual(NumberKind.PLAIN, "plain")
        self.assertEqual(NumberKind.PERCENTAGE, "percentage")
        self.assertEqual(NumberKind.MONEY, "money")
        self.assertEqual(NumberKind.MONTHS, "months")

    def test_tside_enum(self):
        self.assertEqual(Tside.ASSET, 1)
        self.assertEqual(Tside.LIABILITY, 2)

    def test_level_enum(self):
        self.assertEqual(Level.GLOBAL, 1)
        self.assertEqual(Level.TEMPLATE, 2)
        self.assertEqual(Level.INSTANCE, 3)

    def test_features_enum(self):
        self.assertEqual(Features.UNKNOWN_FEATURE, 0)
        self.assertEqual(Features.MANDATES, 1)
        self.assertEqual(Features.MULTIPLE_OWNERS, 3)
        self.assertEqual(Features.CARD, 4)
        self.assertEqual(Features.SUB_ACCOUNTS, 5)
        self.assertEqual(Features.JOINT_ACCOUNT, 6)
        self.assertEqual(Features.INVESTMENT, 7)

    def test_note_type_enum(self):
        self.assertEqual(NoteType.UNKNOWN, 0)
        self.assertEqual(NoteType.RAW_TEXT, 1)
        self.assertEqual(NoteType.REASON_CODE, 2)

    def test_rejected_reason_enum(self):
        self.assertEqual(RejectedReason.UNKNOWN_REASON, 0)
        self.assertEqual(RejectedReason.INSUFFICIENT_FUNDS, 1)
        self.assertEqual(RejectedReason.WRONG_DENOMINATION, 2)
        self.assertEqual(RejectedReason.AGAINST_TNC, 3)
        self.assertEqual(RejectedReason.CLIENT_CUSTOM_REASON, 4)

    def test_update_permission_enum(self):
        self.assertEqual(UpdatePermission.PERMISSION_UNKNOWN, 0)
        self.assertEqual(UpdatePermission.FIXED, 1)
        self.assertEqual(UpdatePermission.OPS_EDITABLE, 2)
        self.assertEqual(UpdatePermission.USER_EDITABLE, 3)
        self.assertEqual(UpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION, 4)

    def test_rejected_exception(self):
        rejected = Rejected("Test rejected", reason_code=RejectedReason.AGAINST_TNC)
        self.assertEqual(rejected.reason_code, RejectedReason.AGAINST_TNC)
        self.assertEqual(str(rejected), "Test rejected")

    def test_flag_timeseries_empty(self):
        flags = FlagTimeseries()
        self.assertFalse(flags.at(timestamp=datetime(2020, 3, 25)))

    def test_flag_timeseries(self):
        flags = FlagTimeseries(
            [
                (datetime(2020, 3, 25, 10, 30), True),
                (datetime(2020, 3, 25, 22, 30), False),
            ]
        )
        self.assertTrue(flags.at(timestamp=datetime(2020, 3, 25, 13, 45)))
        self.assertFalse(flags.at(timestamp=datetime(2020, 3, 25, 23, 15)))

    def test_parameter_global_level(self):
        parameter = Parameter(
            name="day_of_month",
            description="Which day would you like interest to be paid?",
            display_name="Day of month to pay interest",
            level=Level.GLOBAL,
            default_value=27,
            shape=NumberShape(min_value=1, max_value=28, step=1),
        )
        self.assertEqual(parameter.default_value, 27)

    def test_parameter_template_level(self):
        parameter = Parameter(
            name="overdraft_fee",
            description="Overdraft fee",
            display_name="Fee charged for balances over the overdraft limit",
            level=Level.TEMPLATE,
            default_value=Decimal(15),
            shape=NumberShape(kind=NumberKind.MONEY, min_value=0, max_value=100, step=0.01),
        )
        self.assertEqual(parameter.default_value, Decimal(15))

    def test_parameter_instance_level(self):
        parameter = Parameter(
            name="minimum_interest_rate",
            description="Minimum interest rate",
            display_name="Minimum interest rate paid on positive balances",
            level=Level.INSTANCE,
            update_permission=UpdatePermission.FIXED,
            derived=False,
            default_value=Decimal(1.0),
            shape=NumberShape(min_value=0, max_value=100, step=0.01),
        )
        self.assertEqual(parameter.default_value, Decimal(1.0))

    def test_parameter_string_shape(self):
        parameter = Parameter(
            name="string_parameter",
            description="template level string parameter",
            display_name="Test Parameter",
            level=Level.TEMPLATE,
            value="some value",
            shape=StringShape,
        )
        self.assertEqual(parameter.value, "some value")

    def test_parameter_account_id_shape(self):
        parameter = Parameter(
            name="account_id",
            description="template level account id parameter",
            display_name="Test Parameter",
            level=Level.TEMPLATE,
            value="13212354",
            shape=AccountIdShape,
        )
        self.assertEqual(parameter.value, "13212354")

    def test_parameter_denomination_shape(self):
        parameter = Parameter(
            name="denomination",
            description="template level denomination parameter",
            display_name="Test Parameter",
            level=Level.TEMPLATE,
            value="GBP",
            shape=DenominationShape,
        )
        self.assertEqual(parameter.value, "GBP")

    def test_parameter_date_shape(self):
        parameter = Parameter(
            name="bonus_date",
            description="Date account bonus will be paid",
            display_name="Bonus date",
            level=Level.TEMPLATE,
            value=datetime(2020, 3, 27),
            shape=DateShape(min_date=datetime(2020, 1, 1), max_date=datetime(2020, 3, 31)),
        )
        self.assertEqual(parameter.value, datetime(2020, 3, 27))

    def test_parameter_timeseries(self):
        parameter_one = Parameter(
            name="parameter_one",
            description="First parameter",
            display_name="First Parameter",
            level=Level.TEMPLATE,
            value="First value",
            shape=StringShape,
        )
        parameter_two = Parameter(
            name="parameter_two",
            description="Second parameter",
            display_name="Second Parameter",
            level=Level.TEMPLATE,
            value="Second value",
            shape=StringShape,
        )
        parameters = ParameterTimeseries(
            [
                (datetime(2020, 1, 1), parameter_one.value),
                (datetime(2020, 2, 1), parameter_two.value),
            ]
        )
        self.assertEqual(parameters.at(timestamp=datetime(2020, 1, 10)), "First value")
        self.assertEqual(parameters.at(timestamp=datetime(2020, 2, 10)), "Second value")

    def test_posting_instruction_batch_balances_not_implemented(self):
        posting_instruction_batch = PostingInstructionBatch(
            batch_id="batch_id",
            batch_details={},
            client_id="Visa",
            client_batch_id="international-payment",
            value_timestamp=self.TS_300,
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
                    account_id=self.account_id_300,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
        )

        with self.assertRaises(NotImplementedError):
            posting_instruction_batch.balances()

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
