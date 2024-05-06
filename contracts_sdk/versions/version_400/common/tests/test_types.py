from unittest import TestCase
from datetime import datetime, timezone
from contextlib import redirect_stderr
from decimal import Decimal
from io import StringIO
from zoneinfo import ZoneInfo

from ..types import (
    AccountIdShape,
    AddressDetails,
    AdjustmentAmount,
    AuthorisationAdjustment,
    Balance,
    BalanceCoordinate,
    BalanceDefaultDict,
    BalancesFilter,
    BalancesIntervalFetcher,
    BalancesObservation,
    BalancesObservationFetcher,
    BalanceTimeseries,
    CalendarEvent,
    CalendarEvents,
    ClientTransaction,
    ClientTransactionEffects,
    DeactivationHookArguments,
    DeactivationHookResult,
    CustomInstruction,
    DateShape,
    
    DEFAULT_ADDRESS,
    DEFAULT_ASSET,
    DefinedDateTime,
    DenominationShape,
    DerivedParameterHookArguments,
    DerivedParameterHookResult,
    EndOfMonthSchedule,
    
    EventTypesGroup,
    
    fetch_account_data,
    FlagTimeseries,
    InboundAuthorisation,
    InboundHardSettlement,
    AccountNotificationDirective,
    ParameterLevel,
    Logger,
    Next,
    NumberShape,
    OptionalShape,
    OptionalValue,
    OutboundAuthorisation,
    OutboundHardSettlement,
    Override,
    Parameter,
    ParameterTimeseries,
    
    Phase,
    PlanNotificationDirective,
    ActivationHookArguments,
    ActivationHookResult,
    Posting,
    PostingInstructionsDirective,
    PostingInstructionType,
    PostingsIntervalFetcher,
    PostParameterChangeHookArguments,
    PostParameterChangeHookResult,
    PreParameterChangeHookResult,
    PostPostingHookArguments,
    PostPostingHookResult,
    PreParameterChangeHookArguments,
    PrePostingHookArguments,
    PrePostingHookResult,
    Previous,
    Rejection,
    RejectionReason,
    RelativeDateTime,
    Release,
    requires,
    ScheduleExpression,
    ScheduledEventHookArguments,
    ScheduledEvent,
    ScheduledEventHookResult,
    ScheduleFailover,
    ScheduleSkip,
    Settlement,
    Shift,
    SmartContractDescriptor,
    SmartContractEventType,
    
    StringShape,
    SupervisedHooks,
    SupervisionExecutionMode,
    SupervisorActivationHookArguments,
    SupervisorActivationHookResult,
    SupervisorConversionHookArguments,
    SupervisorConversionHookResult,
    SupervisorContractEventType,
    SupervisorPostPostingHookArguments,
    SupervisorPrePostingHookArguments,
    SupervisorPostPostingHookResult,
    SupervisorPrePostingHookResult,
    SupervisorScheduledEventHookArguments,
    SupervisorScheduledEventHookResult,
    TimeseriesItem,
    TransactionCode,
    Transfer,
    Tside,
    UnionItem,
    UnionItemValue,
    UnionShape,
    UpdateAccountEventTypeDirective,
    UpdatePlanEventTypeDirective,
    ParameterUpdatePermission,
    ConversionHookArguments,
    ConversionHookResult,
)
from ..types.postings import _PITypes_str
from .....utils.exceptions import (
    StrongTypingError,
    InvalidSmartContractError,
    InvalidPostingInstructionException,
)
from .....utils import symbols


class PublicCommonV400TypesTestCase(TestCase):
    test_naive_datetime = datetime(year=2021, month=1, day=1)
    test_zoned_datetime_utc = datetime(year=2021, month=1, day=1, tzinfo=ZoneInfo("UTC"))
    test_end_datetime = datetime(year=2021, month=2, day=1, tzinfo=ZoneInfo("UTC"))
    test_account_id = "test_test_account_id"
    version = "400"
    executor_type = "common"
    module_desc = "Common"
    address = "DEFAULT"
    asset = "COMMERCIAL_BANK_MONEY"
    denomination = "GBP"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client_transaction_id_custom = "client_transaction_id_custom"
        cls.client_transaction_id_transfer = "client_transaction_id_transfer"
        cls.client_transaction_id_settle = "client_transaction_id_settle"
        cls.client_id = "client_id"
        cls.account_id = "account_id"
        cls.posting_datetime = datetime(2022, 12, 12, tzinfo=ZoneInfo("UTC"))
        cls.custom_instruction = CustomInstruction(
            postings=[
                Posting(
                    credit=False,
                    amount=Decimal(10),
                    denomination="GBP",
                    account_id=cls.account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ],
            instruction_details={"TYPE": "PURCHASE"},
            transaction_code=TransactionCode(
                domain="something",
                family="other",
                subfamily="same",
            ),
        )
        cls.custom_instruction._set_output_attributes(  # noqa: SLF001
            insertion_datetime=cls.posting_datetime,
            value_datetime=cls.posting_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=[
                Posting(
                    account_id=cls.account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=False,
                    phase=Phase.COMMITTED,
                    amount=Decimal(10),
                    denomination="GBP",
                ),
            ],
            instruction_id="instruction_id_1",
            unique_client_transaction_id=f"{cls.client_id}_{cls.client_transaction_id_custom}",
            own_account_id=cls.account_id,
            tside=Tside.LIABILITY,
        )
        cls.settlement = Settlement(client_transaction_id=cls.client_transaction_id_settle)
        cls.settlement._set_output_attributes(  # noqa: SLF001
            insertion_datetime=cls.posting_datetime,
            value_datetime=cls.posting_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=[
                Posting(
                    account_id=cls.account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=True,
                    phase=Phase.COMMITTED,
                    amount=Decimal(20),
                    denomination="GBP",
                ),
                Posting(
                    account_id=cls.account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=False,
                    phase=Phase.PENDING_IN,
                    amount=Decimal(20),
                    denomination="GBP",
                ),
            ],
            instruction_id="instruction_id_2",
            unique_client_transaction_id=f"{cls.client_id}_{cls.client_transaction_id_settle}",
            target_account_id=cls.account_id,
            own_account_id=cls.account_id,
            tside=Tside.LIABILITY,
        )
        cls.transfer = Transfer(
            creditor_target_account_id=cls.account_id,
            denomination="HKK",
            amount=Decimal(10),
            debtor_target_account_id="1",
        )
        cls.transfer._set_output_attributes(  # noqa: SLF001
            insertion_datetime=cls.posting_datetime,
            value_datetime=cls.posting_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=[
                Posting(
                    account_id=cls.account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=True,
                    phase=Phase.COMMITTED,
                    amount=Decimal(1),
                    denomination="HKK",
                ),
            ],
            instruction_id="instruction_id_3",
            unique_client_transaction_id=f"{cls.client_id}_{cls.client_transaction_id_transfer}",
            own_account_id=cls.account_id,
            tside=Tside.LIABILITY,
        )
        cls.inbound_auth = InboundAuthorisation(
            client_transaction_id=cls.client_transaction_id_settle,
            denomination="GBP",
            target_account_id=cls.account_id,
            amount=Decimal(20),
            internal_account_id="1",
        )
        cls.inbound_auth._set_output_attributes(  # noqa: SLF001
            insertion_datetime=cls.posting_datetime,
            value_datetime=cls.posting_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=[
                Posting(
                    account_id=cls.account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=True,
                    phase=Phase.PENDING_IN,
                    amount=Decimal(20),
                    denomination="GBP",
                ),
            ],
            instruction_id="instruction_id_4",
            unique_client_transaction_id=f"{cls.client_id}_{cls.client_transaction_id_settle}",
            own_account_id=cls.account_id,
            tside=Tside.LIABILITY,
        )
        cls.hard_settle = InboundHardSettlement(
            denomination="GBP", target_account_id="123", amount=Decimal(20), internal_account_id="1"
        )
        cls.hard_settle._set_output_attributes(  # noqa: SLF001
            insertion_datetime=cls.posting_datetime,
            value_datetime=cls.posting_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=[
                Posting(
                    account_id="123",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=True,
                    phase=Phase.COMMITTED,
                    amount=Decimal(20),
                    denomination="GBP",
                ),
            ],
            instruction_id="instruction_id_5",
            unique_client_transaction_id=f"{cls.client_id}_123",
            own_account_id="123",
            tside=Tside.ASSET,
        )
        cls.balance_key_committed = BalanceCoordinate(
            account_address=cls.address,
            asset=cls.asset,
            denomination=cls.denomination,
            phase=Phase.COMMITTED,
        )

    # Parameters

    def test_parameter(self):
        parameter = Parameter(
            name="day_of_month",
            description="Which day would you like interest to be paid?",
            display_name="Day of month to pay interest",
            level=ParameterLevel.GLOBAL,
            default_value=27,
            derived=False,
            shape=NumberShape(min_value=1, max_value=28, step=1),
        )
        self.assertEqual(parameter.default_value, 27)

    def test_parameter_init_validation(self):
        with self.assertRaises(TypeError) as ex:
            Parameter()
        self.assertEqual(
            str(ex.exception),
            "Parameter.__init__() missing 3 required keyword-only arguments: 'name', 'shape', and "
            "'level'",
        )

        with self.assertRaises(StrongTypingError) as ex:
            Parameter(name=None, shape=None, level=None)
        self.assertEqual(str(ex.exception), "Parameter attribute 'name' expected str, got None")

        with self.assertRaises(InvalidSmartContractError) as ex:
            Parameter(name="", shape=StringShape(), level=1)
        self.assertEqual(str(ex.exception), "Parameter attribute 'name' must be a non-empty string")

        with self.assertRaises(StrongTypingError) as ex:
            Parameter(name="name", shape=None, level=None)
        self.assertEqual(
            str(ex.exception),
            "Parameter attribute 'shape' expected Union[AccountIdShape, DateShape, "
            "DenominationShape, NumberShape, OptionalShape, StringShape, UnionShape],"
            " got None",
        )

        with self.assertRaises(StrongTypingError) as ex:
            Parameter(name="name", shape=Decimal, level=None)
        self.assertEqual(
            str(ex.exception),
            "Parameter attribute 'shape' expected Union[AccountIdShape, DateShape, "
            "DenominationShape, NumberShape, OptionalShape, StringShape, UnionShape], got "
            "'<class 'decimal.Decimal'>'",
        )

        with self.assertRaises(StrongTypingError) as ex:
            Parameter(name="name", shape=StringShape, level=None)
        self.assertEqual(
            str(ex.exception),
            "Parameter init arg 'shape' for parameter 'name' must be an instance of the "
            "StringShape class",
        )

        with self.assertRaises(StrongTypingError) as ex:
            Parameter(name="name", shape=StringShape(), level=None)
        self.assertEqual(
            str(ex.exception),
            "Parameter attribute 'level' expected ParameterLevel, got None",
        )

        with self.assertRaises(StrongTypingError) as ex:
            Parameter(name="name", shape=StringShape(), level=1.0)
        self.assertEqual(
            str(ex.exception),
            "Parameter attribute 'level' expected ParameterLevel, got '1.0' of type float",
        )

        with self.assertRaises(StrongTypingError) as ex:
            Parameter(name="name", shape=StringShape(), level=ParameterLevel.INSTANCE, derived=1)
        self.assertEqual(
            str(ex.exception),
            "Parameter attribute 'derived' expected bool if populated, got '1' of type int",
        )

        with self.assertRaises(StrongTypingError) as ex:
            Parameter(
                name="name",
                shape=StringShape(),
                level=ParameterLevel.INSTANCE,
                derived=True,
                display_name=True,
            )
        self.assertEqual(
            str(ex.exception),
            "Parameter attribute 'display_name' expected str if populated, got 'True' of type bool",
        )

        with self.assertRaises(StrongTypingError) as ex:
            Parameter(
                name="name",
                shape=StringShape(),
                level=ParameterLevel.INSTANCE,
                derived=True,
                display_name="display_name",
                description=StringShape(),
            )
        self.assertEqual(
            str(ex.exception),
            "Parameter attribute 'description' expected str if populated, got 'StringShape'",
        )

        with self.assertRaises(StrongTypingError) as ex:
            Parameter(
                name="name",
                shape=StringShape(),
                level=ParameterLevel.INSTANCE,
                derived=True,
                display_name="display_name",
                description="description",
                default_value=StringShape(),
            )
        self.assertEqual(
            str(ex.exception),
            "Parameter attribute 'default_value' expected Union[Decimal, str, datetime, "
            "OptionalValue, UnionItemValue, int] if populated, got 'StringShape'",
        )

        with self.assertRaises(StrongTypingError) as ex:
            Parameter(
                name="name",
                shape=OptionalShape(shape=StringShape()),
                level=ParameterLevel.INSTANCE,
                derived=False,
                display_name="display_name",
                description="description",
                default_value=OptionalValue(Decimal(1)),
                update_permission=True,
            )
        self.assertEqual(
            str(ex.exception),
            "Parameter attribute 'update_permission' expected ParameterUpdatePermission if "
            "populated, got 'True' of type bool",
        )

    def test_parameter_cannot_use_optional_default_value(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            Parameter(
                name="overdraft_limit",
                level=ParameterLevel.TEMPLATE,
                description="Overdraft limit",
                shape=StringShape(),
                default_value=OptionalValue(1),
            )
        self.assertIn(
            "Non optional shapes must have a non optional default value: overdraft_limit",
            str(ex.exception),
        )

    def test_parameter_invalid_default_value_raises_error(self):
        with self.assertRaises(StrongTypingError) as ex:
            Parameter(
                name="overdraft_limit",
                level=ParameterLevel.TEMPLATE,
                description="Overdraft limit",
                shape=StringShape(),
                default_value=500,
            )
        self.assertIn(
            "Expected str, got '500' of type int",
            str(ex.exception),
        )

    def test_parameter_invalid_optional_default_value_raises_error(self):
        with self.assertRaises(StrongTypingError) as ex:
            Parameter(
                name="overdraft_limit",
                level=ParameterLevel.TEMPLATE,
                description="Overdraft limit",
                shape=OptionalShape(shape=StringShape()),
                default_value=500,
            )
        self.assertIn(
            "Expected OptionalValue, got '500' of type int",
            str(ex.exception),
        )

        with self.assertRaises(StrongTypingError) as ex:
            Parameter(
                name="overdraft_limit",
                level=ParameterLevel.TEMPLATE,
                description="Overdraft limit",
                shape=OptionalShape(shape=StringShape()),
                default_value=OptionalValue(500),
            )
        self.assertIn(
            "Expected str, got '500' of type int",
            str(ex.exception),
        )

    def test_optional_value_raises_with_invalid_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            OptionalValue(value=True)
        self.assertEqual(
            "'OptionalValue.value' expected Union[Decimal, str, datetime, UnionItemValue, int] if "
            "populated, got 'True' of type bool",
            str(ex.exception),
        )

    def test_optional_value_raises_with_naive_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            OptionalValue(datetime(2022, 1, 1))
        self.assertEqual(
            "'value' of OptionalValue is not timezone aware.",
            str(ex.exception),
        )

    def test_optional_value_raises_with_non_utc_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            OptionalValue(datetime(2022, 1, 1, tzinfo=ZoneInfo("US/Pacific")))
        self.assertEqual(
            "'value' of OptionalValue must have timezone UTC, currently US/Pacific.",
            str(ex.exception),
        )

    def test_optional_value_raises_with_non_zoneinfo_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            OptionalValue(datetime.fromtimestamp(1, timezone.utc))
        self.assertEqual(
            "'value' of OptionalValue must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(ex.exception),
        )

    def test_parameter_global_level(self):
        parameter = Parameter(
            name="day_of_month",
            description="Which day would you like interest to be paid?",
            display_name="Day of month to pay interest",
            level=ParameterLevel.GLOBAL,
            default_value=27,
            shape=NumberShape(min_value=1, max_value=28, step=1),
        )
        self.assertEqual(parameter.default_value, 27)

    def test_parameter_default_value_raises_with_naive_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            Parameter(
                name="day_of_month",
                description="Which day would you like interest to be paid?",
                display_name="Day of month to pay interest",
                level=ParameterLevel.GLOBAL,
                default_value=datetime(2022, 1, 1),
                shape=DateShape(
                    min_date=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                    max_date=datetime(2020, 3, 31, tzinfo=ZoneInfo("UTC")),
                ),
            )
        self.assertEqual(
            "'default_value' of Parameter is not timezone aware.",
            str(ex.exception),
        )

    def test_parameter_default_value_raises_with_non_utc_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            Parameter(
                name="day_of_month",
                description="Which day would you like interest to be paid?",
                display_name="Day of month to pay interest",
                level=ParameterLevel.GLOBAL,
                default_value=datetime(2022, 1, 1, tzinfo=ZoneInfo("US/Pacific")),
                shape=DateShape(
                    min_date=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                    max_date=datetime(2020, 3, 31, tzinfo=ZoneInfo("UTC")),
                ),
            )
        self.assertEqual(
            "'default_value' of Parameter must have timezone UTC, currently US/Pacific.",
            str(ex.exception),
        )

    def test_parameter_default_value_raises_with_non_zoneinfo_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            Parameter(
                name="day_of_month",
                description="Which day would you like interest to be paid?",
                display_name="Day of month to pay interest",
                level=ParameterLevel.GLOBAL,
                default_value=datetime.fromtimestamp(1, timezone.utc),
                shape=DateShape(
                    min_date=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                    max_date=datetime(2020, 3, 31, tzinfo=ZoneInfo("UTC")),
                ),
            )
        self.assertEqual(
            "'default_value' of Parameter must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(ex.exception),
        )

    def test_parameter_template_level(self):
        parameter = Parameter(
            name="overdraft_fee",
            description="Overdraft fee",
            display_name="Fee charged for balances over the overdraft limit",
            level=ParameterLevel.TEMPLATE,
            default_value=Decimal(15),
            shape=NumberShape(min_value=0, max_value=100, step=Decimal("0.01")),
        )
        self.assertEqual(parameter.default_value, Decimal(15))

    def test_parameter_instance_level(self):
        parameter = Parameter(
            name="minimum_interest_rate",
            description="Minimum interest rate",
            display_name="Minimum interest rate paid on positive balances",
            level=ParameterLevel.INSTANCE,
            update_permission=ParameterUpdatePermission.FIXED,
            derived=False,
            default_value=Decimal(1.0),
            shape=NumberShape(min_value=0, max_value=100, step=Decimal("0.01")),
        )
        self.assertEqual(parameter.default_value, Decimal(1.0))

    def test_parameter_string_shape(self):
        parameter = Parameter(
            name="string_parameter",
            description="template level string parameter",
            display_name="Test Parameter",
            level=ParameterLevel.TEMPLATE,
            shape=StringShape(),
        )
        self.assertTrue(isinstance(parameter.shape, StringShape))

    def test_parameter_account_id_shape(self):
        parameter = Parameter(
            name="account_id",
            description="template level account id parameter",
            display_name="Test Parameter",
            level=ParameterLevel.TEMPLATE,
            shape=AccountIdShape(),
        )
        self.assertTrue(isinstance(parameter.shape, AccountIdShape))

    def test_parameter_denomination_shape(self):
        parameter = Parameter(
            name="denomination",
            description="template level denomination parameter",
            display_name="Test Parameter",
            level=ParameterLevel.TEMPLATE,
            shape=DenominationShape(),
        )
        self.assertTrue(isinstance(parameter.shape, DenominationShape))

    def test_parameter_date_shape(self):
        date_shape = DateShape(
            min_date=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
            max_date=datetime(2020, 3, 31, tzinfo=ZoneInfo("UTC")),
        )
        parameter = Parameter(
            name="bonus_date",
            description="Date account bonus will be paid",
            display_name="Bonus date",
            level=ParameterLevel.TEMPLATE,
            shape=date_shape,
        )
        self.assertEqual(parameter.shape, date_shape)

    def test_parameter_date_shape_min_date_raise_with_naive_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            DateShape(
                min_date=datetime(2020, 1, 1),
                max_date=datetime(2020, 3, 31, tzinfo=ZoneInfo("UTC")),
            )
        self.assertEqual(
            "'min_date' of DateShape is not timezone aware.",
            str(ex.exception),
        )

    def test_parameter_date_shape_min_date_raise_with_non_utc_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            DateShape(
                min_date=datetime(2020, 1, 1, tzinfo=ZoneInfo("US/Pacific")),
                max_date=datetime(2020, 3, 31, tzinfo=ZoneInfo("UTC")),
            )
        self.assertEqual(
            "'min_date' of DateShape must have timezone UTC, currently US/Pacific.",
            str(ex.exception),
        )

    def test_parameter_date_shape_min_date_raise_with_non_zoneinfo_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            DateShape(
                min_date=datetime.fromtimestamp(1, timezone.utc),
                max_date=datetime(2020, 3, 31, tzinfo=ZoneInfo("UTC")),
            )
        self.assertEqual(
            "'min_date' of DateShape must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(ex.exception),
        )

    def test_parameter_date_shape_max_date_raise_with_naive_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            DateShape(
                min_date=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                max_date=datetime(2020, 3, 31),
            )
        self.assertEqual(
            "'max_date' of DateShape is not timezone aware.",
            str(ex.exception),
        )

    def test_parameter_date_shape_max_date_raise_with_non_utc_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            DateShape(
                min_date=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                max_date=datetime(2020, 3, 31, tzinfo=ZoneInfo("US/Pacific")),
            )
        self.assertEqual(
            "'max_date' of DateShape must have timezone UTC, currently US/Pacific.",
            str(ex.exception),
        )

    def test_parameter_date_shape_max_date_raise_with_non_zoneinfo_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            DateShape(
                min_date=datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
                max_date=datetime.fromtimestamp(1, timezone.utc),
            )
        self.assertEqual(
            "'max_date' of DateShape must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(ex.exception),
        )

    def test_parameter_timeseries(self):
        parameters = ParameterTimeseries(
            [
                (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), "First value"),
                (datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")), "Second value"),
            ]
        )
        self.assertEqual(
            "First value", parameters.at(at_datetime=datetime(2020, 1, 10, tzinfo=ZoneInfo("UTC")))
        )
        self.assertEqual(
            "Second value", parameters.at(at_datetime=datetime(2020, 2, 10, tzinfo=ZoneInfo("UTC")))
        )

    def test_parameter_timeseries_raises_with_naive_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            ParameterTimeseries(
                [
                    (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), "First value"),
                    (datetime(2020, 2, 1), "Second value"),
                ]
            )
        self.assertEqual("'at_datetime' of TimeseriesItem is not timezone aware.", str(e.exception))

    def test_parameter_timeseries_raises_with_non_utc_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            ParameterTimeseries(
                [
                    (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), "First value"),
                    (datetime(2020, 2, 1, tzinfo=ZoneInfo("US/Pacific")), "Second value"),
                ]
            )
        self.assertEqual(
            "'at_datetime' of TimeseriesItem must have timezone UTC, currently US/Pacific.",
            str(e.exception),
        )

    def test_parameter_timeseries_raises_with_non_zoneinfo_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            ParameterTimeseries(
                [
                    (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), "First value"),
                    (datetime.fromtimestamp(1, timezone.utc), "Second value"),
                ]
            )
        self.assertEqual(
            str(e.exception),
            "'at_datetime' of TimeseriesItem must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
        )

    def test_parameter_timeseries_at_raises_with_non_utc_timezone(self):
        parameters = ParameterTimeseries(
            [
                (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), "First value"),
                (datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")), "Second value"),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            parameters.at(at_datetime=datetime(2020, 1, 10, tzinfo=ZoneInfo("US/Pacific")))
        self.assertEqual(
            "'at_datetime' of ParameterTimeseries.at() must have timezone UTC, currently US/Pacific.",  # noqa: E501
            str(e.exception),
        )

    def test_parameter_timeseries_at_raises_with_non_zoneinfo_timezone(self):
        parameters = ParameterTimeseries(
            [
                (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), "First value"),
                (datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")), "Second value"),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            parameters.at(at_datetime=datetime.fromtimestamp(1, timezone.utc))
        self.assertEqual(
            "'at_datetime' of ParameterTimeseries.at() must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(e.exception),
        )

    def test_parameter_timeseries_at_raises_with_naive_datetime(self):
        parameters = ParameterTimeseries(
            [
                (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), "First value"),
                (datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")), "Second value"),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            parameters.at(at_datetime=datetime(2020, 1, 10))
        self.assertEqual(
            "'at_datetime' of ParameterTimeseries.at() is not timezone aware.", str(e.exception)
        )

    def test_parameter_timeseries_before_raises_with_non_utc_timezone(self):
        parameters = ParameterTimeseries(
            [
                (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), "First value"),
                (datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")), "Second value"),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            parameters.before(at_datetime=datetime(2020, 1, 10, tzinfo=ZoneInfo("US/Pacific")))
        self.assertEqual(
            "'at_datetime' of ParameterTimeseries.before() must have timezone UTC, currently US/Pacific.",  # noqa: E501
            str(e.exception),
        )

    def test_parameter_timeseries_before_raises_with_non_zoneinfo_timezone(self):
        parameters = ParameterTimeseries(
            [
                (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), "First value"),
                (datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")), "Second value"),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            parameters.before(at_datetime=datetime.fromtimestamp(1, timezone.utc))
        self.assertEqual(
            "'at_datetime' of ParameterTimeseries.before() must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(e.exception),
        )

    def test_parameter_timeseries_before_raises_with_naive_datetime(self):
        parameters = ParameterTimeseries(
            [
                (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), "First value"),
                (datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")), "Second value"),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            parameters.before(at_datetime=datetime(2020, 1, 10))
        self.assertEqual(
            "'at_datetime' of ParameterTimeseries.before() is not timezone aware.", str(e.exception)
        )

    def test_parameter_not_using_shape_instance(self):
        with self.assertRaises(StrongTypingError) as ex:
            Parameter(
                name="day_of_month",
                description="Which day would you like interest to be paid?",
                display_name="Day of month to pay interest",
                level=ParameterLevel.GLOBAL,
                default_value=27,
                derived=False,
                shape=NumberShape,
            )
        self.assertEqual(
            str(ex.exception),
            "Parameter init arg 'shape' for parameter 'day_of_month' must be an instance of the "
            "NumberShape class",
        )

    def test_parameter_invalid_shape(self):
        with self.assertRaises(StrongTypingError) as ex:
            Parameter(
                name="day_of_month",
                description="Which day would you like interest to be paid?",
                display_name="Day of month to pay interest",
                level=ParameterLevel.GLOBAL,
                default_value=27,
                derived=False,
                shape=Decimal,
            )
        self.assertEqual(
            str(ex.exception),
            "Parameter attribute 'shape' expected Union[AccountIdShape, DateShape, "
            "DenominationShape, NumberShape, OptionalShape, StringShape, UnionShape], got "
            "'<class 'decimal.Decimal'>'",
        )

    def test_derived_parameters_cannot_have_default_values(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            Parameter(
                name="overdraft_limit",
                level=ParameterLevel.INSTANCE,
                description="Overdraft limit",
                shape=StringShape(),
                default_value="1",
                derived=True,
            )
        self.assertIn(
            "Derived Parameters cannot have a default value or update permissions: "
            "overdraft_limit",
            str(ex.exception),
        )

    def test_parameter_default_value_multiple_optional_value(self):
        with self.assertRaises(StrongTypingError) as ex:
            Parameter(
                name="day_of_month",
                description="Which day would you like interest to be paid?",
                display_name="Day of month to pay interest",
                level=ParameterLevel.GLOBAL,
                derived=False,
                shape=OptionalShape(shape=NumberShape()),
                default_value=OptionalValue(OptionalValue(1)),
            )
        self.assertEqual(
            str(ex.exception),
            "'OptionalValue.value' expected Union[Decimal, str, datetime, UnionItemValue, int] if "
            "populated, got 'OptionalValue'",
        )

    def test_parameter_timeseries_all_method(self):
        parameters = ParameterTimeseries(
            [
                (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), "First value"),
                (datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")), "Second value"),
            ]
        )
        self.assertIsInstance(
            parameters.all(),
            ParameterTimeseries,
            "ParameterTimeseries.all() must be of type ParameterTimeseries",
        )
        self.assertEqual(len(parameters.all()), 2)
        self.assertEqual(
            parameters.all()[0],
            TimeseriesItem((datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), "First value")),
        )
        self.assertEqual(
            parameters.all()[1],
            TimeseriesItem((datetime(2020, 2, 1, tzinfo=ZoneInfo("UTC")), "Second value")),
        )

    def test_parameter_timeseries_all_get_attributes(self):
        parameters = ParameterTimeseries(
            [
                (datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")), "First value"),
            ]
        )
        self.assertEqual(len(parameters.all()), 1)

        timeseries_item = parameters.all()[0]
        self.assertEqual(timeseries_item.at_datetime, datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")))
        self.assertEqual(timeseries_item.value, "First value")

    # Shapes

    def test_number_shape_init(self):
        with self.assertRaises(StrongTypingError) as ex:
            NumberShape(min_value="")
        self.assertEqual(
            str(ex.exception),
            "'min_value' expected Union[Decimal, int] if populated, got '' " "of type str",
        )

        with self.assertRaises(StrongTypingError) as ex:
            NumberShape(min_value=1, max_value="")
        self.assertEqual(
            str(ex.exception),
            "'max_value' expected Union[Decimal, int] if populated, got '' of type str",
        )

        with self.assertRaises(StrongTypingError) as ex:
            NumberShape(min_value=1, max_value=2, step="")
        self.assertEqual(
            str(ex.exception),
            "'step' expected Union[Decimal, int] if populated, got '' of type str",
        )

        with self.assertRaises(InvalidSmartContractError) as ex:
            NumberShape(min_value=2, max_value=1)
        self.assertEqual(str(ex.exception), "NumberShape min_value must be less than max_value")

        valid_number_shape = NumberShape(min_value=1, max_value=2, step=Decimal(0.01))
        self.assertEqual(valid_number_shape.min_value, 1)
        self.assertEqual(valid_number_shape.max_value, 2)
        self.assertEqual(valid_number_shape.step, Decimal(0.01))

    def test_date_shape_init(self):
        with self.assertRaises(StrongTypingError) as ex:
            DateShape(min_date="")
        self.assertEqual(
            str(ex.exception), "'min_date' expected datetime if populated, got '' of type str"
        )

        with self.assertRaises(StrongTypingError) as ex:
            DateShape(min_date=datetime(1999, 1, 1, tzinfo=ZoneInfo("UTC")), max_date="")
        self.assertEqual(
            str(ex.exception), "'max_date' expected datetime if populated, got '' of type str"
        )

        with self.assertRaises(InvalidSmartContractError) as ex:
            DateShape(
                min_date=datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC")),
                max_date=datetime(1999, 1, 1, tzinfo=ZoneInfo("UTC")),
            )
        self.assertEqual(str(ex.exception), "DateShape min_date must be less than max_date")

        valid_date_shape_1 = DateShape()
        valid_date_shape_2 = DateShape(min_date=datetime(1999, 1, 1, tzinfo=ZoneInfo("UTC")))
        valid_date_shape_3 = DateShape(max_date=datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC")))

        self.assertEqual(valid_date_shape_1.min_date, None)
        self.assertEqual(valid_date_shape_1.max_date, None)
        self.assertEqual(valid_date_shape_2.min_date, datetime(1999, 1, 1, tzinfo=ZoneInfo("UTC")))
        self.assertEqual(valid_date_shape_2.max_date, None)
        self.assertEqual(valid_date_shape_3.min_date, None)
        self.assertEqual(valid_date_shape_3.max_date, datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC")))

    def test_union_shape_init(self):
        with self.assertRaises(TypeError) as ex:
            UnionShape()
        self.assertEqual(
            str(ex.exception),
            "UnionShape.__init__() missing 1 required keyword-only argument: 'items'",
        )

        with self.assertRaises(StrongTypingError) as ex:
            UnionShape(items=1)
        self.assertEqual(
            str(ex.exception),
            "UnionShape __init__ Expected list of UnionItem objects for " "'items', got '1'",
        )

        with self.assertRaises(InvalidSmartContractError) as ex:
            UnionShape(items=[])
        self.assertEqual(str(ex.exception), "'items' must be a non empty list, got []")

        with self.assertRaises(StrongTypingError) as ex:
            UnionShape(items=[1, 2, 3])
        self.assertEqual(
            str(ex.exception), "UnionShape __init__ Expected UnionItem, got '1' of type int"
        )

        union_item = UnionItem(key="key", display_name="display_name")
        valid_union_shape = UnionShape(items=[union_item])
        self.assertEqual(valid_union_shape.items[0], union_item)

    def test_union_item_init(self):
        with self.assertRaises(StrongTypingError) as ex:
            UnionItem(key=None, display_name=None)
        self.assertEqual(str(ex.exception), "UnionItem init arg 'key' must be populated")

        with self.assertRaises(StrongTypingError) as ex:
            UnionItem(key="", display_name=None)
        self.assertEqual(str(ex.exception), "UnionItem init arg 'key' must be populated")

        with self.assertRaises(StrongTypingError) as ex:
            UnionItem(key="KEY", display_name=None)
        self.assertEqual(str(ex.exception), "UnionItem init arg 'display_name' must be populated")

        with self.assertRaises(StrongTypingError) as ex:
            UnionItem(key="KEY", display_name="")
        self.assertEqual(str(ex.exception), "UnionItem init arg 'display_name' must be populated")

        valid_union_item = UnionItem(key="KEY", display_name="display_name")
        self.assertEqual(valid_union_item.key, "KEY")
        self.assertEqual(valid_union_item.display_name, "display_name")

    def test_optional_shape_init(self):
        with self.assertRaises(TypeError) as ex:
            OptionalShape()
        self.assertEqual(
            str(ex.exception),
            "OptionalShape.__init__() missing 1 required keyword-only argument: 'shape'",
        )

        with self.assertRaises(TypeError) as ex:
            OptionalShape(1)
        self.assertEqual(
            str(ex.exception),
            "OptionalShape.__init__() takes 1 positional argument but 2 were given",
        )

        with self.assertRaises(StrongTypingError) as ex:
            OptionalShape(shape=1)
        self.assertEqual(
            str(ex.exception),
            "'shape' expected Union[AccountIdShape, DateShape, DenominationShape, NumberShape, "
            "StringShape, UnionShape], got '1' of type int",
        )

        with self.assertRaises(StrongTypingError) as ex:
            OptionalShape(shape=StringShape)
        self.assertEqual(
            str(ex.exception),
            "OptionalShape init arg 'shape' must be an instance of StringShape class",
        )

        shape = StringShape()
        valid_optional_shape = OptionalShape(shape=shape)
        self.assertEqual(valid_optional_shape.shape, shape)

    def test_optional_value_init(self):
        with self.assertRaises(StrongTypingError) as ex:
            OptionalValue(AccountIdShape())
        self.assertEqual(
            str(ex.exception),
            "'OptionalValue.value' expected Union[Decimal, str, datetime, UnionItemValue, int] if "
            "populated, got 'AccountIdShape'",
        )

        with self.assertRaises(StrongTypingError) as ex:
            OptionalValue([])
        self.assertEqual(
            str(ex.exception),
            "'OptionalValue.value' expected Union[Decimal, str, datetime, UnionItemValue, int] if "
            "populated, got '[]' of type list",
        )

        self.assertEqual(OptionalValue("").value, "")

        valid_optional_value = OptionalValue(1)
        self.assertEqual(valid_optional_value.value, 1)
        self.assertEqual(valid_optional_value.is_set(), True)
        valid_optional_value.value = None
        self.assertEqual(valid_optional_value.is_set(), False)

    # Enums

    def test_posting_instrucion_type_enum(self):
        self.assertEqual(PostingInstructionType.AUTHORISATION.value, "Authorisation")
        self.assertEqual(
            PostingInstructionType.AUTHORISATION_ADJUSTMENT.value,
            "AuthorisationAdjustment",
        )
        self.assertEqual(PostingInstructionType.CUSTOM_INSTRUCTION.value, "CustomInstruction")
        self.assertEqual(PostingInstructionType.HARD_SETTLEMENT.value, "HardSettlement")
        self.assertEqual(PostingInstructionType.RELEASE.value, "Release")
        self.assertEqual(PostingInstructionType.SETTLEMENT.value, "Settlement")
        self.assertEqual(PostingInstructionType.TRANSFER.value, "Transfer")

    def test_phase_enum(self):
        self.assertEqual(Phase.PENDING_IN.value, "pending_in")
        self.assertEqual(Phase.PENDING_OUT.value, "pending_out")
        self.assertEqual(Phase.COMMITTED.value, "committed")

    def test_tside_enum(self):
        self.assertEqual(Tside.ASSET.value, 1)
        self.assertEqual(Tside.LIABILITY.value, 2)

    def test_level_enum(self):
        self.assertEqual(ParameterLevel.GLOBAL.value, 1)
        self.assertEqual(ParameterLevel.TEMPLATE.value, 2)
        self.assertEqual(ParameterLevel.INSTANCE.value, 3)

    def test_rejection_reason_enum(self):
        self.assertEqual(RejectionReason.UNKNOWN_REASON.value, 0)
        self.assertEqual(RejectionReason.INSUFFICIENT_FUNDS.value, 1)
        self.assertEqual(RejectionReason.WRONG_DENOMINATION.value, 2)
        self.assertEqual(RejectionReason.AGAINST_TNC.value, 3)
        self.assertEqual(RejectionReason.CLIENT_CUSTOM_REASON.value, 4)

    def test_update_permission_enum(self):
        self.assertEqual(ParameterUpdatePermission.PERMISSION_UNKNOWN.value, 0)
        self.assertEqual(ParameterUpdatePermission.FIXED.value, 1)
        self.assertEqual(ParameterUpdatePermission.OPS_EDITABLE.value, 2)
        self.assertEqual(ParameterUpdatePermission.USER_EDITABLE.value, 3)
        self.assertEqual(ParameterUpdatePermission.USER_EDITABLE_WITH_OPS_PERMISSION.value, 4)

    def test_supervision_execution_mode_enum(self):
        self.assertEqual(SupervisionExecutionMode.OVERRIDE.value, 1)
        self.assertEqual(SupervisionExecutionMode.INVOKED.value, 2)

    # SupervisorActivationHookResult

    def test_supervisor_activation_hook_result(self):
        scheduled_events_return_value = {
            "event_1": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(1970, 1, 1, second=2, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(
                    year="2000",
                    month="1",
                    day="1",
                    hour="0",
                    minute="0",
                    second="0",
                ),
                skip=ScheduleSkip(
                    end=datetime(1970, 1, 1, second=3, tzinfo=ZoneInfo("UTC")),
                ),
            ),
            "event_2": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=5, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(1970, 1, 1, second=6, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(
                    day_of_week="mon",
                ),
            ),
        }
        supervisor_activation_hook_result = SupervisorActivationHookResult(
            scheduled_events_return_value=scheduled_events_return_value
        )
        self.assertEqual(
            scheduled_events_return_value,
            supervisor_activation_hook_result.scheduled_events_return_value,
        )

    def test_supervisor_activation_hook_result_no_events(self):
        supervisor_activation_hook_result = SupervisorActivationHookResult()
        self.assertEqual({}, supervisor_activation_hook_result.scheduled_events_return_value)

    # FlagTimeseries

    def test_flag_timeseries_empty(self):
        flags = FlagTimeseries()
        self.assertFalse(flags.at(at_datetime=datetime(2020, 3, 25, tzinfo=ZoneInfo("UTC"))))

    def test_flag_timeseries(self):
        flags = FlagTimeseries(
            [
                (datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC")), True),
                (datetime(2020, 3, 25, 22, 30, tzinfo=ZoneInfo("UTC")), False),
            ]
        )
        self.assertTrue(flags.at(at_datetime=datetime(2020, 3, 25, 13, 45, tzinfo=ZoneInfo("UTC"))))
        self.assertFalse(
            flags.at(at_datetime=datetime(2020, 3, 25, 23, 15, tzinfo=ZoneInfo("UTC")))
        )

    def test_flag_timeseries_raises_with_naive_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            FlagTimeseries(
                [
                    (datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC")), True),
                    (datetime(2020, 3, 25, 22, 30), False),
                ]
            )
        self.assertEqual("'at_datetime' of TimeseriesItem is not timezone aware.", str(e.exception))

    def test_flag_timeseries_raises_with_non_utc_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            FlagTimeseries(
                [
                    (datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC")), True),
                    (datetime(2020, 3, 25, 22, 30, tzinfo=ZoneInfo("US/Pacific")), False),
                ]
            )
        self.assertEqual(
            "'at_datetime' of TimeseriesItem must have timezone UTC, currently US/Pacific.",
            str(e.exception),
        )

    def test_flag_timeseries_raises_with_non_zoneinfo_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            FlagTimeseries(
                [
                    (datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC")), True),
                    (datetime.fromtimestamp(1, timezone.utc), False),
                ]
            )
        self.assertEqual(
            "'at_datetime' of TimeseriesItem must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(e.exception),
        )

    def test_flag_timeseries_at_raises_with_naive_datetime(self):
        flags = FlagTimeseries(
            [
                (datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC")), True),
                (datetime(2020, 3, 25, 22, 30, tzinfo=ZoneInfo("UTC")), False),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            flags.at(at_datetime=datetime(2020, 3, 25, 13, 45))
        self.assertEqual(
            "'at_datetime' of FlagTimeseries.at() is not timezone aware.", str(e.exception)
        )

    def test_flag_timeseries_at_raises_with_non_utc_timezone(self):
        flags = FlagTimeseries(
            [
                (datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC")), True),
                (datetime(2020, 3, 25, 22, 30, tzinfo=ZoneInfo("UTC")), False),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            flags.at(at_datetime=datetime(2020, 3, 25, 13, 45, tzinfo=ZoneInfo("US/Pacific")))
        self.assertEqual(
            "'at_datetime' of FlagTimeseries.at() must have timezone UTC, currently US/Pacific.",
            str(e.exception),
        )

    def test_flag_timeseries_at_raises_with_non_zoneinfo_timezone(self):
        flags = FlagTimeseries(
            [
                (datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC")), True),
                (datetime(2020, 3, 25, 22, 30, tzinfo=ZoneInfo("UTC")), False),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            flags.at(at_datetime=datetime.fromtimestamp(1, timezone.utc))
        self.assertEqual(
            "'at_datetime' of FlagTimeseries.at() must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(e.exception),
        )

    def test_flag_timeseries_before_raises_with_naive_datetime(self):
        flags = FlagTimeseries(
            [
                (datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC")), True),
                (datetime(2020, 3, 25, 22, 30, tzinfo=ZoneInfo("UTC")), False),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            flags.before(at_datetime=datetime(2020, 3, 25, 13, 45))
        self.assertEqual(
            "'at_datetime' of FlagTimeseries.before() is not timezone aware.", str(e.exception)
        )

    def test_flag_timeseries_before_raises_with_non_utc_timezone(self):
        flags = FlagTimeseries(
            [
                (datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC")), True),
                (datetime(2020, 3, 25, 22, 30, tzinfo=ZoneInfo("UTC")), False),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            flags.before(at_datetime=datetime(2020, 3, 25, 13, 45, tzinfo=ZoneInfo("US/Pacific")))
        self.assertEqual(
            "'at_datetime' of FlagTimeseries.before() must have timezone UTC, currently US/Pacific.",  # noqa: E501
            str(e.exception),
        )

    def test_flag_timeseries_before_raises_with_non_zoneinfo_timezone(self):
        flags = FlagTimeseries(
            [
                (datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC")), True),
                (datetime(2020, 3, 25, 22, 30, tzinfo=ZoneInfo("UTC")), False),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            flags.before(at_datetime=datetime.fromtimestamp(1, timezone.utc))
        self.assertEqual(
            "'at_datetime' of FlagTimeseries.before() must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(e.exception),
        )

    def test_flag_timeseries_all_method(self):
        flags = FlagTimeseries(
            [
                (datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC")), True),
                (datetime(2020, 3, 25, 22, 30, tzinfo=ZoneInfo("UTC")), False),
            ]
        )
        self.assertIsInstance(
            flags.all(), FlagTimeseries, "FlagTimeseries.all() must be of type FlagTimeseries"
        )
        self.assertEqual(len(flags.all()), 2)
        self.assertEqual(
            flags.all()[0],
            TimeseriesItem((datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC")), True)),
        )
        self.assertEqual(
            flags.all()[1],
            TimeseriesItem((datetime(2020, 3, 25, 22, 30, tzinfo=ZoneInfo("UTC")), False)),
        )

    def test_flag_timeseries_all_get_attributes(self):
        flags = FlagTimeseries(
            [
                (datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC")), True),
            ]
        )
        self.assertEqual(len(flags.all()), 1)

        timeseries_item = flags.all()[0]
        self.assertEqual(
            timeseries_item.at_datetime, datetime(2020, 3, 25, 10, 30, tzinfo=ZoneInfo("UTC"))
        )
        self.assertEqual(timeseries_item.value, True)

    # ScheduleExpression

    def test_schedule_expression_can_be_created(self):
        schedule_expression = ScheduleExpression(day="day", year="year")
        self.assertEqual(schedule_expression.day, "day")
        self.assertEqual(schedule_expression.year, "year")

    def test_schedule_expression_int_values(self):
        schedule_expression = ScheduleExpression(
            day=15,
            day_of_week=3,
            hour=30,
            minute=30,
            second=30,
            month=6,
            year=2000,
        )
        self.assertEqual(schedule_expression.day, 15)
        self.assertEqual(schedule_expression.day_of_week, 3)
        self.assertEqual(schedule_expression.hour, 30)
        self.assertEqual(schedule_expression.minute, 30)
        self.assertEqual(schedule_expression.second, 30)
        self.assertEqual(schedule_expression.month, 6)
        self.assertEqual(schedule_expression.year, 2000)

    def test_schedule_expression_zero_values(self):
        schedule_expression = ScheduleExpression(
            hour=0,
        )
        self.assertEqual(schedule_expression.hour, 0)
        # Defaults
        self.assertIsNone(schedule_expression.day)
        self.assertIsNone(schedule_expression.day_of_week)
        self.assertIsNone(schedule_expression.minute)
        self.assertIsNone(schedule_expression.second)
        self.assertIsNone(schedule_expression.month)
        self.assertIsNone(schedule_expression.year)

    def test_schedule_expression_string_values(self):
        schedule_expression = ScheduleExpression(
            day="*/2",
            day_of_week="MON",
            hour="1,2,3",
            minute="*/15",
            second="*/30",
            month="*",
            year="*",
        )
        self.assertEqual(schedule_expression.day, "*/2")
        self.assertEqual(schedule_expression.day_of_week, "MON")
        self.assertEqual(schedule_expression.hour, "1,2,3")
        self.assertEqual(schedule_expression.minute, "*/15")
        self.assertEqual(schedule_expression.second, "*/30")
        self.assertEqual(schedule_expression.month, "*")
        self.assertEqual(schedule_expression.year, "*")

    def test_schedule_expression_invalid_type_day(self):
        with self.assertRaises(StrongTypingError) as ex:
            ScheduleExpression(
                day=False,
                year=2000,
            )
        expected = "'day' expected Union[int, str] if populated, got 'False' of type bool"
        self.assertEqual(expected, str(ex.exception))

    def test_schedule_expression_invalid_type_day_of_week(self):
        with self.assertRaises(StrongTypingError) as ex:
            ScheduleExpression(
                day_of_week=False,
                month=6,
            )
        expected = "'day_of_week' expected Union[int, str] if populated, got 'False' of type bool"
        self.assertEqual(expected, str(ex.exception))

    def test_schedule_expression_invalid_type_hour(self):
        with self.assertRaises(StrongTypingError) as ex:
            ScheduleExpression(
                day=15,
                hour=(),
            )
        expected = "'hour' expected Union[int, str] if populated, got '()' of type tuple"
        self.assertEqual(expected, str(ex.exception))

    def test_schedule_expression_invalid_type_minute(self):
        with self.assertRaises(StrongTypingError) as ex:
            ScheduleExpression(
                hour=30,
                minute={},
            )
        expected = "'minute' expected Union[int, str] if populated, got '{}' of type dict"
        self.assertEqual(expected, str(ex.exception))

    def test_schedule_expression_invalid_type_second(self):
        with self.assertRaises(StrongTypingError) as ex:
            ScheduleExpression(
                second=False,
            )
        expected = "'second' expected Union[int, str] if populated, got 'False' of type bool"
        self.assertEqual(expected, str(ex.exception))

    def test_schedule_expression_invalid_type_month(self):
        with self.assertRaises(StrongTypingError) as ex:
            ScheduleExpression(
                month=False,
                year=2000,
            )
        expected = "'month' expected Union[int, str] if populated, got 'False' of type bool"
        self.assertEqual(expected, str(ex.exception))

    def test_schedule_expression_invalid_type_year(self):
        with self.assertRaises(StrongTypingError) as ex:
            ScheduleExpression(
                year=False,
            )
        expected = "'year' expected Union[int, str] if populated, got 'False' of type bool"
        self.assertEqual(expected, str(ex.exception))

    def test_empty_schedule_expression_raises(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            ScheduleExpression()
        expected = "Empty ScheduleExpression not allowed"
        self.assertEqual(expected, str(ex.exception))

    def test_event_types_group_can_be_created(self):
        event_types_group = EventTypesGroup(
            name="TestEventTypesGroup", event_types_order=["EVENT_TYPE1", "EVENT_TYPE2"]
        )
        self.assertEqual(event_types_group.name, "TestEventTypesGroup")
        self.assertEqual(event_types_group.event_types_order, ["EVENT_TYPE1", "EVENT_TYPE2"])

    def test_event_types_group_empty_name(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            EventTypesGroup(name="", event_types_order=["EVENT_TYPE1", "EVENT_TYPE2"])
        self.assertIn("EventTypesGroup 'name' must be populated", str(ex.exception))

    def test_event_types_group_raises_with_empty_event_types_order(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            EventTypesGroup(name="TestEvenTypesGroup", event_types_order=[])
        self.assertIn("'event_types_order' must be a non empty list, got []", str(ex.exception))

    def test_event_types_group_not_enough_event_types(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            EventTypesGroup(name="TestEvenTypesGroup", event_types_order=["EVENT_TYPE"])
        self.assertIn("An EventTypesGroup must have at least two event types", str(ex.exception))

    # UpdateAccountEventTypeDirective

    def test_update_account_event_type_directive_can_be_created(self):
        update_account_event_type_directive = UpdateAccountEventTypeDirective(
            event_type="event_type_1",
            end_datetime=self.test_zoned_datetime_utc,
        )
        self.assertEqual(update_account_event_type_directive.event_type, "event_type_1")
        self.assertEqual(
            update_account_event_type_directive.end_datetime, self.test_zoned_datetime_utc
        )

    def test_update_account_event_type_directive_raises_with_naive_end_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdateAccountEventTypeDirective(
                event_type="event_type_1",
                end_datetime=self.test_naive_datetime,
            )
        self.assertIn(
            "'end_datetime' of UpdateAccountEventTypeDirective is not timezone aware.",
            str(ex.exception),
        )

    def test_update_account_event_type_directive_raises_with_naive_skip_end_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdateAccountEventTypeDirective(
                event_type="event_type_1",
                skip=ScheduleSkip(end=self.test_naive_datetime),
            )
        self.assertEqual(
            "'end' of ScheduleSkip is not timezone aware.",
            str(ex.exception),
        )

    def test_update_account_event_type_directive_no_end_datetime_or_schedule(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdateAccountEventTypeDirective(
                event_type="event_type_1",
            )

        self.assertIn(
            "UpdateAccountEventTypeDirective object must "
            "have either an end_datetime, an expression",
            str(ex.exception),
        )

    def test_update_account_event_type_directive_with_schedule_method(self):
        schedule_method = EndOfMonthSchedule(day=1)
        update_account_event_type_directive = UpdateAccountEventTypeDirective(
            event_type="event_type_1",
            schedule_method=schedule_method,
        )
        self.assertEqual(update_account_event_type_directive.event_type, "event_type_1")
        self.assertEqual(update_account_event_type_directive.schedule_method, schedule_method)

    def test_update_account_event_type_directive_validation(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdateAccountEventTypeDirective(
                event_type="event_type_1",
                schedule_method=EndOfMonthSchedule(day=1),
                expression=ScheduleExpression(day="1"),
            )
        self.assertEqual(
            "UpdateAccountEventTypeDirective cannot contain both"
            " expression and schedule_method fields",
            str(ex.exception),
        )

    def test_update_account_event_type_directive_invalid_end_datetime(self):
        with self.assertRaises(StrongTypingError) as ex:
            UpdateAccountEventTypeDirective(
                event_type="event_type_1",
                end_datetime=False,
            )
        self.assertEqual("Expected datetime, got 'False' of type bool", str(ex.exception))

    def test_update_account_event_type_directive_skip_indefinitely(self):
        update_account_event_type_directive = UpdateAccountEventTypeDirective(
            event_type="event_type_1",
            skip=True,
        )
        self.assertTrue(update_account_event_type_directive.skip)

    def test_update_account_event_type_directive_skip_some_time(self):
        update_account_event_type_directive = UpdateAccountEventTypeDirective(
            event_type="event_type_1",
            skip=ScheduleSkip(
                end=datetime(year=2021, month=6, day=28, tzinfo=ZoneInfo("US/Pacific"))
            ),
        )
        self.assertEqual(
            datetime(year=2021, month=6, day=28, tzinfo=ZoneInfo("US/Pacific")),
            update_account_event_type_directive.skip.end,
        )

    def test_update_account_event_type_directive_unskip(self):
        update_account_event_type_directive = UpdateAccountEventTypeDirective(
            event_type="event_type_1",
            skip=False,
        )
        self.assertFalse(update_account_event_type_directive.skip)

    def test_update_account_event_type_directive_skip_invalid_end(self):
        with self.assertRaises(StrongTypingError) as ex:
            UpdateAccountEventTypeDirective(
                event_type="event_type_1",
                skip=ScheduleSkip(end=False),
            )
        self.assertEqual("Expected datetime, got 'False' of type bool", str(ex.exception))

    # CalendarEvent

    def test_calendar_event(self):
        calendar_event = CalendarEvent(
            id="test 1",
            calendar_id="123",
            start_datetime=datetime(2015, 1, 1, tzinfo=ZoneInfo("UTC")),
            end_datetime=datetime(2015, 1, 2, tzinfo=ZoneInfo("UTC")),
        )
        self.assertEqual("test 1", calendar_event.id)

    def test_calendar_event_start_datetime_raises_with_naive_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            CalendarEvent(
                id="test 1",
                calendar_id="123",
                start_datetime=datetime(2015, 1, 1),
                end_datetime=datetime(2015, 1, 2, tzinfo=ZoneInfo("UTC")),
            )
        self.assertEqual(
            "'start_datetime' of CalendarEvent is not timezone aware.",
            str(ex.exception),
        )

    def test_calendar_event_start_datetime_raises_with_non_utc_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            CalendarEvent(
                id="test 1",
                calendar_id="123",
                start_datetime=datetime(2015, 1, 1, tzinfo=ZoneInfo("US/Pacific")),
                end_datetime=datetime(2015, 1, 2, tzinfo=ZoneInfo("UTC")),
            )
        self.assertEqual(
            "'start_datetime' of CalendarEvent must have timezone UTC, currently US/Pacific.",
            str(ex.exception),
        )

    def test_calendar_event_start_datetime_raises_with_non_zoneinfo_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            CalendarEvent(
                id="test 1",
                calendar_id="123",
                start_datetime=datetime.fromtimestamp(1, timezone.utc),
                end_datetime=datetime(2015, 1, 2, tzinfo=ZoneInfo("UTC")),
            )
        self.assertEqual(
            "'start_datetime' of CalendarEvent must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(ex.exception),
        )

    def test_calendar_event_end_datetime_raises_with_naive_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            CalendarEvent(
                id="test 1",
                calendar_id="123",
                start_datetime=datetime(2015, 1, 1, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(2015, 1, 2),
            )
        self.assertEqual(
            "'end_datetime' of CalendarEvent is not timezone aware.",
            str(ex.exception),
        )

    def test_calendar_event_end_datetime_raises_with_non_utc_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            CalendarEvent(
                id="test 1",
                calendar_id="123",
                start_datetime=datetime(2015, 1, 1, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(2015, 1, 2, tzinfo=ZoneInfo("US/Pacific")),
            )
        self.assertEqual(
            "'end_datetime' of CalendarEvent must have timezone UTC, currently US/Pacific.",
            str(ex.exception),
        )

    def test_calendar_event_end_datetime_raises_with_non_zoneinfo_timezone(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            CalendarEvent(
                id="test 1",
                calendar_id="123",
                start_datetime=datetime(2015, 1, 1, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime.fromtimestamp(1, timezone.utc),
            )
        self.assertEqual(
            "'end_datetime' of CalendarEvent must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(ex.exception),
        )

    def test_calendar_events(self):
        calendar_events = CalendarEvents(
            calendar_events=[
                CalendarEvent(
                    id="test 1",
                    calendar_id="123",
                    start_datetime=datetime(2015, 1, 1, tzinfo=ZoneInfo("UTC")),
                    end_datetime=datetime(2015, 1, 2, tzinfo=ZoneInfo("UTC")),
                ),
                CalendarEvent(
                    id="test 2",
                    calendar_id="124",
                    start_datetime=datetime(2016, 1, 1, tzinfo=ZoneInfo("UTC")),
                    end_datetime=datetime(2016, 1, 2, tzinfo=ZoneInfo("UTC")),
                ),
            ]
        )
        self.assertEqual(2, len(calendar_events))
        self.assertEqual("test 1", calendar_events[0].id)
        self.assertEqual("test 2", calendar_events[1].id)

    # TransactionCode

    def test_transaction_code(self):
        transaction_code = TransactionCode(
            domain="Blossom",
            family="Buttercup",
            subfamily="Bubbles",
        )
        self.assertEqual("Blossom", transaction_code.domain)

    def test_transaction_code_raises_with_domain_not_populated(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            TransactionCode(
                domain="",
                family="Buttercup",
                subfamily="Bubbles",
            )
        self.assertEqual(
            str(ex.exception),
            "'TransactionCode.domain' must be a non-empty string",
        )

    def test_transaction_code_raises_with_domain_incorrect_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            TransactionCode(
                domain=5,
                family="Buttercup",
                subfamily="Bubbles",
            )
        self.assertEqual(
            str(ex.exception),
            "'TransactionCode.domain' expected str, got '5' of type int",
        )

    def test_transaction_code_raises_with_domain_none(self):
        with self.assertRaises(StrongTypingError) as ex:
            TransactionCode(
                domain=None,
                family="Buttercup",
                subfamily="Bubbles",
            )
        self.assertEqual(
            str(ex.exception),
            "'TransactionCode.domain' expected str, got None",
        )

    def test_transaction_code_raises_with_family_not_populated(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            TransactionCode(
                domain="Blossom",
                family="",
                subfamily="Bubbles",
            )
        self.assertEqual(
            str(ex.exception),
            "'TransactionCode.family' must be a non-empty string",
        )

    def test_transaction_code_raises_with_family_invalid_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            TransactionCode(
                domain="Blossom",
                family=5,
                subfamily="Bubbles",
            )
        self.assertEqual(
            str(ex.exception),
            "'TransactionCode.family' expected str, got '5' of type int",
        )

    def test_transaction_code_raises_with_family_none(self):
        with self.assertRaises(StrongTypingError) as ex:
            TransactionCode(
                domain="Blossom",
                family=None,
                subfamily="Bubbles",
            )
        self.assertEqual(
            str(ex.exception),
            "'TransactionCode.family' expected str, got None",
        )

    def test_transaction_code_raises_with_subfamily_not_populated(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            TransactionCode(
                domain="Blossom",
                family="Buttercup",
                subfamily="",
            )
        self.assertEqual(
            str(ex.exception),
            "'TransactionCode.subfamily' must be a non-empty string",
        )

    def test_transaction_code_raises_with_subfamily_invalid_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            TransactionCode(
                domain="Blossom",
                family="Buttercup",
                subfamily=5,
            )
        self.assertEqual(
            str(ex.exception),
            "'TransactionCode.subfamily' expected str, got '5' of type int",
        )

    def test_transaction_code_raises_with_subfamily_none(self):
        with self.assertRaises(StrongTypingError) as ex:
            TransactionCode(
                domain="Blossom",
                family="Buttercup",
                subfamily=None,
            )
        self.assertEqual(
            str(ex.exception),
            "'TransactionCode.subfamily' expected str, got None",
        )

    def test_transaction_code_raises_with_domain_not_set(self):
        with self.assertRaises(TypeError):
            TransactionCode(
                family="Family",
                subfamily="Sub-Family",
            )

    def test_transaction_code_raises_with_family_not_set(self):
        with self.assertRaises(TypeError):
            TransactionCode(
                domain="Domain",
                subfamily="Sub-Family",
            )

    def test_transaction_code_raises_with_subfamily_not_set(self):
        with self.assertRaises(TypeError):
            TransactionCode(
                domain="Domain",
                family="Family",
            )

    # DeactivationHookArguments

    def test_deactivation_hook_arguments_attributes_can_be_set(self):
        hook_args = DeactivationHookArguments(effective_datetime=self.test_zoned_datetime_utc)
        self.assertEquals(hook_args.effective_datetime, self.test_zoned_datetime_utc)

    def test_only_set_deactivation_hook_arguments_attributes_can_be_accessed(self):
        hook_args = DeactivationHookArguments(effective_datetime=self.test_zoned_datetime_utc)
        self.assertEquals(hook_args.__dict__, {"effective_datetime": self.test_zoned_datetime_utc})

    def test_deactivation_hook_arguments_attributes_not_set_cant_be_accessed(self):
        hook_args = DeactivationHookArguments(effective_datetime=self.test_zoned_datetime_utc)
        self.assertRaises(AttributeError, getattr, hook_args, "old_parameter_values")

    def test_deactivation_hook_arguments_spec(self):
        hook_args = DeactivationHookArguments(effective_datetime=self.test_zoned_datetime_utc)
        public_attributes = hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001

        self.assertEquals(len(public_attributes), 1)
        effective_datetime_attribute = public_attributes[0]
        self.assertEquals(effective_datetime_attribute.name, "effective_datetime")
        self.assertEquals(effective_datetime_attribute.type, "datetime")

    def test_deactivation_hook_arguments_raises_with_naive_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            DeactivationHookArguments(
                effective_datetime=self.test_naive_datetime,
            )
        expected = "'effective_datetime' of DeactivationHookArguments is not timezone aware."
        self.assertEquals(expected, str(ex.exception))

    def test_deactivation_hook_arguments_raises_with_non_utc_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            DeactivationHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
            )
        expected = "'effective_datetime' of DeactivationHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    # DerivedParameterHookArguments

    def test_derived_parameters_arguments_attributes_can_be_set(self):
        hook_args = DerivedParameterHookArguments(effective_datetime=self.test_zoned_datetime_utc)
        self.assertEquals(hook_args.effective_datetime, self.test_zoned_datetime_utc)

    def test_only_set_derived_parameters_arguments_attributes_can_be_accessed(self):
        hook_args = DerivedParameterHookArguments(effective_datetime=self.test_zoned_datetime_utc)
        self.assertEquals(hook_args.__dict__, {"effective_datetime": self.test_zoned_datetime_utc})

    def test_derived_parameters_arguments_attributes_not_set_cant_be_accessed(self):
        hook_args = DerivedParameterHookArguments(effective_datetime=self.test_zoned_datetime_utc)
        self.assertRaises(AttributeError, getattr, hook_args, "old_parameter_values")

    def test_derived_parameters_spec(self):
        hook_args = DerivedParameterHookArguments(effective_datetime=self.test_zoned_datetime_utc)

        spec = hook_args._spec(language_code=symbols.Languages.ENGLISH)  # noqa: SLF001
        public_attributes_dict = {
            attribute.name: attribute
            for attribute in hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001
        }

        self.assertEquals(spec.name, "DerivedParameterHookArguments")
        self.assertEquals(spec.public_attributes.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.constructor.args.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.public_methods, {})

    def test_derived_parameters_arguments_public_attributes(self):
        hook_args = DerivedParameterHookArguments(effective_datetime=self.test_zoned_datetime_utc)

        public_attributes = hook_args._public_attributes(  # noqa: SLF001
            language_code=symbols.Languages.ENGLISH
        )

        self.assertEquals(len(public_attributes), 1)
        effective_datetime_attribute = public_attributes[0]
        self.assertEquals(effective_datetime_attribute.name, "effective_datetime")
        self.assertEquals(effective_datetime_attribute.type, "datetime")

    def test_derived_parameters_hook_arguments_raises_with_naive_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            DerivedParameterHookArguments(
                effective_datetime=self.test_naive_datetime,
            )
        expected = "'effective_datetime' of DerivedParameterHookArguments is not timezone aware."
        self.assertEquals(expected, str(ex.exception))

    def test_derived_parameters_hook_arguments_raises_with_non_utc_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            DerivedParameterHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
            )
        expected = "'effective_datetime' of DerivedParameterHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    # SupervisorActivationHookArguments

    def test_supervisor_activation_hook_arguments_attributes_can_be_set(self):
        hook_args = SupervisorActivationHookArguments(
            effective_datetime=self.test_zoned_datetime_utc
        )
        self.assertEqual(self.test_zoned_datetime_utc, hook_args.effective_datetime)

    def test_only_set_supervisor_activation_hook_arguments_attributes_can_be_accessed(self):
        hook_args = SupervisorActivationHookArguments(
            effective_datetime=self.test_zoned_datetime_utc
        )
        self.assertEqual({"effective_datetime": self.test_zoned_datetime_utc}, hook_args.__dict__)
        self.assertRaises(AttributeError, getattr, hook_args, "old_parameter_values")

    def test_supervisor_activation_hook_arguments_spec(self):
        hook_args = SupervisorActivationHookArguments(
            effective_datetime=self.test_zoned_datetime_utc
        )
        spec = hook_args._spec(language_code=symbols.Languages.ENGLISH)  # noqa: SLF001
        public_attributes_dict = {
            attribute.name: attribute
            for attribute in hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001
        }
        self.assertEqual("SupervisorActivationHookArguments", spec.name)
        self.assertEqual(public_attributes_dict.keys(), spec.public_attributes.keys())
        self.assertEqual(public_attributes_dict.keys(), spec.constructor.args.keys())
        self.assertEqual({}, spec.public_methods)

    def test_supervisor_activation_hook_arguments_public_attributes(self):
        hook_args = SupervisorActivationHookArguments(
            effective_datetime=self.test_zoned_datetime_utc
        )
        public_attributes = hook_args._public_attributes(  # noqa: SLF001
            language_code=symbols.Languages.ENGLISH
        )

        self.assertEqual(1, len(public_attributes))
        effective_datetime_attribute = public_attributes[0]
        self.assertEqual("effective_datetime", effective_datetime_attribute.name)
        self.assertEqual("datetime", effective_datetime_attribute.type)

    def test_supervisor_activation_hook_arguments_raises_with_naive_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorActivationHookArguments(
                effective_datetime=self.test_naive_datetime,
            )
        expected = (
            "'effective_datetime' of SupervisorActivationHookArguments is not timezone aware."
        )
        self.assertEquals(expected, str(ex.exception))

    def test_supervisor_activation_hook_arguments_raises_with_non_utc_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorActivationHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
            )
        expected = "'effective_datetime' of SupervisorActivationHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    # SupervisorConversionHookArguments

    def test_supervisor_conversion_hook_arguments_attributes_can_be_set(self):
        existing_schedules = {
            "test_event": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(day="5"),
            ),
        }
        hook_args = SupervisorConversionHookArguments(
            effective_datetime=self.test_zoned_datetime_utc, existing_schedules=existing_schedules
        )
        self.assertEqual(self.test_zoned_datetime_utc, hook_args.effective_datetime)
        self.assertEquals(existing_schedules, hook_args.existing_schedules)

    def test_only_set_supervisor_conversion_hook_arguments_attributes_can_be_accessed(self):
        existing_schedules = {
            "test_event": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(day="5"),
            ),
        }
        hook_args = SupervisorConversionHookArguments(
            effective_datetime=self.test_zoned_datetime_utc, existing_schedules=existing_schedules
        )
        self.assertEquals(
            {
                "effective_datetime": self.test_zoned_datetime_utc,
                "existing_schedules": existing_schedules,
            },
            hook_args.__dict__,
        )
        self.assertRaises(AttributeError, getattr, hook_args, "old_parameter_values")

    def test_supervisor_conversion_hook_arguments_spec(self):
        existing_schedules = {
            "test_event": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(day="5"),
            ),
        }
        hook_args = SupervisorConversionHookArguments(
            effective_datetime=self.test_zoned_datetime_utc, existing_schedules=existing_schedules
        )
        spec = hook_args._spec(language_code=symbols.Languages.ENGLISH)  # noqa: SLF001
        public_attributes_dict = {
            attribute.name: attribute
            for attribute in hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001
        }

        self.assertEqual("SupervisorConversionHookArguments", spec.name)
        self.assertEqual(public_attributes_dict.keys(), spec.public_attributes.keys())
        self.assertEqual(public_attributes_dict.keys(), spec.constructor.args.keys())
        self.assertEqual({}, spec.public_methods)

    def test_supervisor_conversion_hook_arguments_public_attributes(self):
        existing_schedules = {
            "test_event": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(day="5"),
            ),
        }
        hook_args = SupervisorConversionHookArguments(
            effective_datetime=self.test_zoned_datetime_utc, existing_schedules=existing_schedules
        )

        public_attributes = hook_args._public_attributes(  # noqa: SLF001
            language_code=symbols.Languages.ENGLISH
        )
        self.assertEqual(2, len(public_attributes))
        effective_datetime_attribute = public_attributes[0]
        self.assertEquals("effective_datetime", effective_datetime_attribute.name)
        self.assertEquals("datetime", effective_datetime_attribute.type)
        existing_schedules_attribute = public_attributes[1]
        self.assertEquals("existing_schedules", existing_schedules_attribute.name)
        self.assertEquals("Dict[str, ScheduledEvent]", existing_schedules_attribute.type)

    def test_supervisor_conversion_hook_arguments_raises_with_naive_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorConversionHookArguments(
                effective_datetime=self.test_naive_datetime,
                existing_schedules={},
            )
        expected = (
            "'effective_datetime' of SupervisorConversionHookArguments is not timezone aware."
        )
        self.assertEquals(expected, str(ex.exception))

    def test_supervisor_conversion_hook_arguments_raises_with_non_utc_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorConversionHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
                existing_schedules={},
            )
        expected = "'effective_datetime' of SupervisorConversionHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    # ActivationHookArguments

    def test_post_activate_code_arguments_attributes_can_be_set(self):
        hook_args = ActivationHookArguments(effective_datetime=self.test_zoned_datetime_utc)
        self.assertEquals(hook_args.effective_datetime, self.test_zoned_datetime_utc)

    def test_only_set_post_activate_code_arguments_attributes_can_be_accessed(self):
        hook_args = ActivationHookArguments(effective_datetime=self.test_zoned_datetime_utc)
        self.assertEquals(hook_args.__dict__, {"effective_datetime": self.test_zoned_datetime_utc})

    def test_post_activate_code_arguments_attributes_not_set_cant_be_accessed(self):
        hook_args = ActivationHookArguments(effective_datetime=self.test_zoned_datetime_utc)
        self.assertRaises(AttributeError, getattr, hook_args, "old_parameter_values")

    def test_post_activate_code_spec(self):
        hook_args = ActivationHookArguments(effective_datetime=self.test_zoned_datetime_utc)

        spec = hook_args._spec(language_code=symbols.Languages.ENGLISH)  # noqa: SLF001
        public_attributes_dict = {
            attribute.name: attribute
            for attribute in hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001
        }

        self.assertEquals(spec.name, "ActivationHookArguments")
        self.assertEquals(spec.public_attributes.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.constructor.args.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.public_methods, {})

    def test_post_activate_code_arguments_public_attributes(self):
        hook_args = ActivationHookArguments(effective_datetime=self.test_zoned_datetime_utc)

        public_attributes = hook_args._public_attributes(  # noqa: SLF001
            language_code=symbols.Languages.ENGLISH
        )

        self.assertEquals(len(public_attributes), 1)
        effective_datetime_attribute = public_attributes[0]
        self.assertEquals(effective_datetime_attribute.name, "effective_datetime")
        self.assertEquals(effective_datetime_attribute.type, "datetime")

    def test_post_activate_code_hook_arguments_raises_with_naive_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            ActivationHookArguments(
                effective_datetime=self.test_naive_datetime,
            )
        expected = "'effective_datetime' of ActivationHookArguments is not timezone aware."
        self.assertEquals(expected, str(ex.exception))

    def test_post_activate_code_hook_arguments_raises_with_non_utc_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            ActivationHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
            )
        expected = "'effective_datetime' of ActivationHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    # ConversionHookArguments

    def test_conversion_hook_arguments_attributes_can_be_set(self):
        existing_schedules = {
            "test_event": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(day="5"),
            ),
        }
        hook_args = ConversionHookArguments(
            effective_datetime=self.test_zoned_datetime_utc, existing_schedules=existing_schedules
        )
        self.assertEquals(self.test_zoned_datetime_utc, hook_args.effective_datetime)
        self.assertEquals(existing_schedules, hook_args.existing_schedules)

    def test_only_set_conversion_hook_arguments_attributes_can_be_accessed(self):
        existing_schedules = {
            "test_event": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(day="5"),
            ),
        }
        hook_args = ConversionHookArguments(
            effective_datetime=self.test_zoned_datetime_utc, existing_schedules=existing_schedules
        )
        self.assertEquals(
            {
                "effective_datetime": self.test_zoned_datetime_utc,
                "existing_schedules": existing_schedules,
            },
            hook_args.__dict__,
        )
        self.assertRaises(AttributeError, getattr, hook_args, "old_parameter_values")

    def test_conversion_hook_arguments_spec(self):
        existing_schedules = {
            "test_event": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(day="5"),
            ),
        }
        hook_args = ConversionHookArguments(
            effective_datetime=self.test_zoned_datetime_utc, existing_schedules=existing_schedules
        )

        spec = hook_args._spec(language_code=symbols.Languages.ENGLISH)  # noqa: SLF001
        public_attributes_dict = {
            attribute.name: attribute
            for attribute in hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001
        }

        self.assertEquals("ConversionHookArguments", spec.name)
        self.assertEquals(public_attributes_dict.keys(), spec.public_attributes.keys())
        self.assertEquals(public_attributes_dict.keys(), spec.constructor.args.keys())
        self.assertEquals({}, spec.public_methods)

    def test_conversion_hook_arguments_public_attributes(self):
        existing_schedules = {
            "test_event": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(day="5"),
            ),
        }
        hook_args = ConversionHookArguments(
            effective_datetime=self.test_zoned_datetime_utc, existing_schedules=existing_schedules
        )

        public_attributes = hook_args._public_attributes(  # noqa: SLF001
            language_code=symbols.Languages.ENGLISH
        )

        self.assertEquals(2, len(public_attributes))
        effective_datetime_attribute = public_attributes[0]
        self.assertEquals("effective_datetime", effective_datetime_attribute.name)
        self.assertEquals("datetime", effective_datetime_attribute.type)
        existing_schedules_attribute = public_attributes[1]
        self.assertEquals("existing_schedules", existing_schedules_attribute.name)
        self.assertEquals("Dict[str, ScheduledEvent]", existing_schedules_attribute.type)

    def test_conversion_hook_arguments_raises_with_naive_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            ConversionHookArguments(
                effective_datetime=self.test_naive_datetime,
                existing_schedules={},
            )
        expected = "'effective_datetime' of ConversionHookArguments is not timezone aware."
        self.assertEquals(expected, str(ex.exception))

    def test_conversion_hook_arguments_raises_with_non_utc_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            ConversionHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
                existing_schedules={},
            )
        expected = "'effective_datetime' of ConversionHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    # PostParameterChangeHookArguments

    def test_post_parameter_change_hook_arguments_attributes_can_be_set(self):
        old_parameter_values = {"param1": "old_val1", "param2": "old_val2"}
        updated_parameter_values = {"param1": "new_val1", "param2": "new_val2"}
        hook_args = PostParameterChangeHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            old_parameter_values=old_parameter_values,
            updated_parameter_values=updated_parameter_values,
        )
        self.assertEquals(hook_args.effective_datetime, self.test_zoned_datetime_utc)
        self.assertEquals(hook_args.old_parameter_values, old_parameter_values)
        self.assertEquals(hook_args.updated_parameter_values, updated_parameter_values)

    def test_only_set_post_parameter_change_hook_arguments_attributes_can_be_accessed(self):
        old_parameter_values = {"param1": "old_val1", "param2": "old_val2"}
        updated_parameter_values = {"param1": "new_val1", "param2": "new_val2"}
        hook_args = PostParameterChangeHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            old_parameter_values=old_parameter_values,
            updated_parameter_values=updated_parameter_values,
        )
        self.assertEquals(
            hook_args.__dict__,
            {
                "effective_datetime": self.test_zoned_datetime_utc,
                "old_parameter_values": old_parameter_values,
                "updated_parameter_values": updated_parameter_values,
            },
        )

    def test_post_parameter_change_hook_arguments_attributes_not_set_cant_be_accessed(self):
        old_parameter_values = {"param1": "old_val1", "param2": "old_val2"}
        updated_parameter_values = {"param1": "new_val1", "param2": "new_val2"}
        hook_args = PostParameterChangeHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            old_parameter_values=old_parameter_values,
            updated_parameter_values=updated_parameter_values,
        )
        self.assertRaises(AttributeError, getattr, hook_args, "postings")

    def test_post_parameter_change_hook_spec(self):
        old_parameter_values = {"param1": "old_val1", "param2": "old_val2"}
        updated_parameter_values = {"param1": "new_val1", "param2": "new_val2"}
        hook_args = PostParameterChangeHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            old_parameter_values=old_parameter_values,
            updated_parameter_values=updated_parameter_values,
        )
        spec = hook_args._spec(language_code=symbols.Languages.ENGLISH)  # noqa: SLF001
        public_attributes_dict = {
            attribute.name: attribute
            for attribute in hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001
        }

        self.assertEquals(spec.name, "PostParameterChangeHookArguments")
        self.assertEquals(spec.public_attributes.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.constructor.args.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.public_methods, {})

    def test_post_parameter_change_hook_arguments_public_attributes(self):
        old_parameter_values = {"param1": "old_val1", "param2": "old_val2"}
        updated_parameter_values = {"param1": "new_val1", "param2": "new_val2"}
        hook_args = PostParameterChangeHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            old_parameter_values=old_parameter_values,
            updated_parameter_values=updated_parameter_values,
        )
        public_attributes = hook_args._public_attributes(  # noqa: SLF001
            language_code=symbols.Languages.ENGLISH
        )

        self.assertEquals(len(public_attributes), 3)
        effective_datetime_attr, old_param_vals_attr, updated_param_vals_attr = public_attributes

        self.assertEquals(effective_datetime_attr.name, "effective_datetime")
        self.assertEquals(effective_datetime_attr.type, "datetime")

        self.assertEquals(old_param_vals_attr.name, "old_parameter_values")
        self.assertEquals(
            old_param_vals_attr.type,
            "Dict[str, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]",
        )

        self.assertEquals(updated_param_vals_attr.name, "updated_parameter_values")
        self.assertEquals(
            updated_param_vals_attr.type,
            "Dict[str, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]",
        )

    def test_post_parameter_change_hook_arguments_raises_with_naive_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            PostParameterChangeHookArguments(
                effective_datetime=self.test_naive_datetime,
                old_parameter_values={},
                updated_parameter_values={},
            )
        expected = "'effective_datetime' of PostParameterChangeHookArguments is not timezone aware."
        self.assertEquals(expected, str(ex.exception))

    def test_post_parameter_change_arguments_raises_with_non_utc_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            PostParameterChangeHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
                old_parameter_values={},
                updated_parameter_values={},
            )
        expected = "'effective_datetime' of PostParameterChangeHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    # Posting

    def test_posting_class_attributes(self):
        posting = Posting(
            credit=True,
            denomination="GBP",
            account_address="DEFAULT",
            account_id="1",
            amount=Decimal(10),
            asset="DEFAULT",
            phase=Phase.COMMITTED,
        )
        self.assertEquals(posting.credit, True)
        self.assertEquals(posting.denomination, "GBP")
        self.assertEquals(posting.account_address, "DEFAULT")
        self.assertEquals(posting.account_id, "1")
        self.assertEquals(posting.amount, Decimal(10))
        self.assertEquals(posting.asset, "DEFAULT")
        self.assertEquals(posting.phase, Phase.COMMITTED)

    def test_posting_class_attributes_invalid_phase(self):
        with self.assertRaises(StrongTypingError) as e:
            Posting(
                credit=True,
                denomination="GBP",
                account_address="DEFAULT",
                account_id="1",
                amount=Decimal(10),
                asset="DEFAULT",
                phase="not a phase",
            )
        self.assertEqual("'phase' must be set to a Phase value", str(e.exception))

    def test_posting_class_attributes_missing(self):
        with self.assertRaises(TypeError) as ex:
            Posting()

        self.assertIn(
            (
                "Posting.__init__() missing 7 required keyword-only arguments: 'credit', 'amount', "
                "'denomination', 'account_id', 'account_address', 'asset', and 'phase'"
            ),
            str(ex.exception),
        )

    def test_posting_class_attributes_empty(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            Posting(
                credit=True,
                denomination="",
                account_address="",
                account_id="",
                amount=Decimal(10),
                asset="",
                phase=Phase.COMMITTED,
            )

        self.assertIn(
            (
                "Postings missing required argument(s): "
                "['denomination', 'account_id', 'account_address', 'asset']"
            ),
            str(ex.exception),
        )

    def test_posting_class_attributes_skips_validation(self):
        # InvalidSmartContractError not raised
        Posting(
            credit=True,
            denomination="",
            account_address="",
            account_id="",
            amount=Decimal(10),
            asset="",
            phase=Phase.COMMITTED,
            _from_proto=True,
        )

    def test_posting_class_raises_with_negative_amount(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            Posting(
                credit=True,
                denomination="GBP",
                account_address="DEFAULT",
                account_id="1",
                amount=Decimal(-10),
                asset="DEFAULT",
                phase=Phase.COMMITTED,
            )

        self.assertIn("Amount must be greater than 0, -10", str(ex.exception))

    # PostPostingHookArguments

    def test_post_posting_hook_arguments_attributes_different_pi_types(self):
        custom_ctx = ClientTransaction(
            client_transaction_id=self.client_transaction_id_custom,
            account_id=self.account_id,
            posting_instructions=[self.custom_instruction],
            tside=Tside.LIABILITY,
        )
        settle_ctx = ClientTransaction(
            client_transaction_id=self.client_transaction_id_settle,
            account_id=self.account_id,
            posting_instructions=[self.inbound_auth, self.settlement],
            tside=Tside.LIABILITY,
        )
        transfer_ctx = ClientTransaction(
            client_transaction_id=self.client_transaction_id_transfer,
            account_id=self.account_id,
            posting_instructions=[self.transfer],
            tside=Tside.LIABILITY,
        )
        hook_args = PostPostingHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            posting_instructions=[self.custom_instruction, self.settlement, self.transfer],
            client_transactions={
                f"{self.client_id}_{self.client_transaction_id_custom}": custom_ctx,
                f"{self.client_id}_{self.client_transaction_id_settle}": settle_ctx,
                f"{self.client_id}_{self.client_transaction_id_transfer}": transfer_ctx,
            },
        )
        self.assertEquals(hook_args.effective_datetime, self.test_zoned_datetime_utc)
        self.assertEquals(
            hook_args.posting_instructions,
            [self.custom_instruction, self.settlement, self.transfer],
        )
        # Check that balances() method on individual PIs
        self.assertEqual(
            hook_args.posting_instructions[0].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(0), debit=Decimal(10), net=Decimal("-10")),
        )
        self.assertEqual(
            hook_args.posting_instructions[1].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(0), net=Decimal("20")),
        )
        self.assertEqual(
            hook_args.posting_instructions[1].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                )
            ],
            Balance(credit=Decimal(0), debit=Decimal(20), net=Decimal("-20")),
        )
        self.assertEqual(
            hook_args.posting_instructions[2].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="HKK",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(1), debit=Decimal(0), net=Decimal("1")),
        )
        # Check that balances() method on individual ClientTransactions
        self.assertEqual(
            hook_args.client_transactions[
                f"{self.client_id}_{self.client_transaction_id_custom}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(0), debit=Decimal(10), net=Decimal("-10")),
        )
        self.assertEqual(
            hook_args.client_transactions[
                f"{self.client_id}_{self.client_transaction_id_settle}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0)),
        )
        self.assertEqual(
            hook_args.client_transactions[
                f"{self.client_id}_{self.client_transaction_id_settle}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(0), net=Decimal("20")),
        )
        self.assertEqual(
            hook_args.client_transactions[
                f"{self.client_id}_{self.client_transaction_id_transfer}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="HKK",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(1), debit=Decimal(0), net=Decimal("1")),
        )

    def test_post_posting_hook_raises_with_naive_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            PostPostingHookArguments(
                effective_datetime=self.test_naive_datetime,
                posting_instructions=[],
                client_transactions={},
            )
        expected = "'effective_datetime' of PostPostingHookArguments is not timezone aware."
        self.assertEquals(expected, str(ex.exception))

    def test_post_posting_hook_raises_with_non_utc_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            PostPostingHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
                posting_instructions=[],
                client_transactions={},
            )
        expected = "'effective_datetime' of PostPostingHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    def test_post_posting_hook_spec(self):
        hook_args = PostPostingHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            posting_instructions=[],
            client_transactions={},
        )
        spec = hook_args._spec(language_code=symbols.Languages.ENGLISH)  # noqa: SLF001
        public_attributes_dict = {
            attribute.name: attribute
            for attribute in hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001
        }

        self.assertEquals(spec.name, "PostPostingHookArguments")
        self.assertEquals(spec.public_attributes.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.constructor.args.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.public_methods, {})

        public_attributes = spec.public_attributes

        self.assertEquals(len(public_attributes), 3)
        effective_datetime, posting_instructions, client_transactions = public_attributes.values()

        self.assertEquals(effective_datetime.name, "effective_datetime")
        self.assertEquals(effective_datetime.type, "datetime")

        self.assertEquals(posting_instructions.name, "posting_instructions")
        self.assertEquals(posting_instructions.type, _PITypes_str)

        self.assertEquals(client_transactions.name, "client_transactions")
        self.assertEquals(client_transactions.type, "Dict[str, ClientTransaction]")

    # SupervisorPostPostingCodeArguments

    def test_supervisor_post_posting_hook_arguments_attributes_can_be_set(self):
        custom_ctx = ClientTransaction(
            client_transaction_id=self.client_transaction_id_custom,
            account_id=self.account_id,
            posting_instructions=[self.custom_instruction],
            tside=Tside.LIABILITY,
        )
        settle_ctx = ClientTransaction(
            client_transaction_id=self.client_transaction_id_settle,
            account_id=self.account_id,
            posting_instructions=[self.inbound_auth, self.settlement],
            tside=Tside.LIABILITY,
        )
        transfer_ctx = ClientTransaction(
            client_transaction_id=self.client_transaction_id_transfer,
            account_id=self.account_id,
            posting_instructions=[self.transfer],
            tside=Tside.LIABILITY,
        )
        hard_settle_ctx = ClientTransaction(
            client_transaction_id="123",
            account_id="123",
            posting_instructions=[self.hard_settle],
            tside=Tside.ASSET,
        )
        hook_args = SupervisorPostPostingHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            supervisee_posting_instructions={
                self.account_id: [self.custom_instruction, self.settlement, self.transfer],
                "123": [self.hard_settle],
            },
            supervisee_client_transactions={
                self.account_id: {
                    f"{self.client_id}_{self.client_transaction_id_custom}": custom_ctx,
                    f"{self.client_id}_{self.client_transaction_id_settle}": settle_ctx,
                    f"{self.client_id}_{self.client_transaction_id_transfer}": transfer_ctx,
                },
                "123": {
                    f"{self.client_id}_123": hard_settle_ctx,
                },
            },
        )
        self.assertEquals(hook_args.effective_datetime, self.test_zoned_datetime_utc)
        self.assertEquals(
            hook_args.supervisee_posting_instructions,
            {
                self.account_id: [self.custom_instruction, self.settlement, self.transfer],
                "123": [self.hard_settle],
            },
        )
        self.assertEqual(
            hook_args.supervisee_client_transactions,
            {
                self.account_id: {
                    f"{self.client_id}_{self.client_transaction_id_custom}": custom_ctx,
                    f"{self.client_id}_{self.client_transaction_id_settle}": settle_ctx,
                    f"{self.client_id}_{self.client_transaction_id_transfer}": transfer_ctx,
                },
                "123": {
                    f"{self.client_id}_123": hard_settle_ctx,
                },
            },
        )
        # Check that balances() method on individual PIs for each supervisee
        self.assertEqual(
            hook_args.supervisee_posting_instructions[self.account_id][0].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(0), debit=Decimal(10), net=Decimal("-10")),
        )
        self.assertEqual(
            hook_args.supervisee_posting_instructions[self.account_id][1].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(0), net=Decimal("20")),
        )
        self.assertEqual(
            hook_args.supervisee_posting_instructions[self.account_id][1].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                )
            ],
            Balance(credit=Decimal(0), debit=Decimal(20), net=Decimal("-20")),
        )
        self.assertEqual(
            hook_args.supervisee_posting_instructions[self.account_id][2].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="HKK",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(1), debit=Decimal(0), net=Decimal("1")),
        )
        self.assertEqual(
            hook_args.supervisee_posting_instructions["123"][0].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(0), net=Decimal("-20")),
        )
        # Check that balances() method on individual ClientTransactions
        self.assertEqual(
            hook_args.supervisee_client_transactions[self.account_id][
                f"{self.client_id}_{self.client_transaction_id_custom}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(0), debit=Decimal(10), net=Decimal("-10")),
        )
        self.assertEqual(
            hook_args.supervisee_client_transactions[self.account_id][
                f"{self.client_id}_{self.client_transaction_id_settle}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0)),
        )
        self.assertEqual(
            hook_args.supervisee_client_transactions[self.account_id][
                f"{self.client_id}_{self.client_transaction_id_settle}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(0), net=Decimal("20")),
        )
        self.assertEqual(
            hook_args.supervisee_client_transactions[self.account_id][
                f"{self.client_id}_{self.client_transaction_id_transfer}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="HKK",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(1), debit=Decimal(0), net=Decimal("1")),
        )
        self.assertEqual(
            hook_args.supervisee_client_transactions["123"][f"{self.client_id}_123"].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(0), net=Decimal("-20")),
        )

    def test_supervisor_post_posting_hook_raises_with_naive_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorPostPostingHookArguments(
                effective_datetime=self.test_naive_datetime,
                supervisee_posting_instructions={},
                supervisee_client_transactions={},
            )
        expected = (
            "'effective_datetime' of SupervisorPostPostingHookArguments is not timezone aware."
        )
        self.assertEquals(expected, str(ex.exception))

    def test_supervisor_post_posting_hook_raises_with_non_utc_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorPostPostingHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
                supervisee_posting_instructions={},
                supervisee_client_transactions={},
            )
        expected = "'effective_datetime' of SupervisorPostPostingHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    def test_supervisor_post_posting_hook_spec(self):
        hook_args = SupervisorPostPostingHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            supervisee_posting_instructions={},
            supervisee_client_transactions={},
        )
        spec = hook_args._spec(language_code=symbols.Languages.ENGLISH)  # noqa: SLF001

        public_attributes_dict = {
            attribute.name: attribute
            for attribute in hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001
        }

        self.assertEqual(spec.name, "SupervisorPostPostingHookArguments")
        self.assertEqual(spec.public_attributes.keys(), public_attributes_dict.keys())
        self.assertEqual(spec.constructor.args.keys(), public_attributes_dict.keys())
        self.assertEqual(spec.public_methods, {})

        public_attributes = spec.public_attributes

        self.assertEquals(len(public_attributes), 3)
        effective_datetime, postings, client_transactions = public_attributes.values()

        self.assertEquals(effective_datetime.name, "effective_datetime")
        self.assertEquals(effective_datetime.type, "datetime")

        self.assertEquals(postings.name, "supervisee_posting_instructions")
        self.assertEquals(postings.type, f"Dict[str, {_PITypes_str}]")

        self.assertEquals(client_transactions.name, "supervisee_client_transactions")
        self.assertEquals(client_transactions.type, "Dict[str, Dict[str, ClientTransaction]]")

    # PrePostingHookArguments

    def test_pre_posting_hook_arguments_attributes_can_be_set(self):
        custom_ctx = ClientTransaction(
            client_transaction_id=self.client_transaction_id_custom,
            account_id=self.account_id,
            posting_instructions=[self.custom_instruction],
            tside=Tside.LIABILITY,
        )
        settle_ctx = ClientTransaction(
            client_transaction_id=self.client_transaction_id_settle,
            account_id=self.account_id,
            posting_instructions=[self.inbound_auth, self.settlement],
            tside=Tside.LIABILITY,
        )
        transfer_ctx = ClientTransaction(
            client_transaction_id=self.client_transaction_id_transfer,
            account_id=self.account_id,
            posting_instructions=[self.transfer],
            tside=Tside.LIABILITY,
        )
        hook_args = PrePostingHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            posting_instructions=[self.custom_instruction, self.settlement, self.transfer],
            client_transactions={
                f"{self.client_id}_{self.client_transaction_id_custom}": custom_ctx,
                f"{self.client_id}_{self.client_transaction_id_settle}": settle_ctx,
                f"{self.client_id}_{self.client_transaction_id_transfer}": transfer_ctx,
            },
        )
        self.assertEquals(hook_args.effective_datetime, self.test_zoned_datetime_utc)
        self.assertEquals(
            hook_args.posting_instructions,
            [self.custom_instruction, self.settlement, self.transfer],
        )
        # Check that balances() method on individual PIs
        self.assertEqual(
            hook_args.posting_instructions[0].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(0), debit=Decimal(10), net=Decimal("-10")),
        )
        self.assertEqual(
            hook_args.posting_instructions[1].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(0), net=Decimal("20")),
        )
        self.assertEqual(
            hook_args.posting_instructions[1].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                )
            ],
            Balance(credit=Decimal(0), debit=Decimal(20), net=Decimal("-20")),
        )
        self.assertEqual(
            hook_args.posting_instructions[2].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="HKK",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(1), debit=Decimal(0), net=Decimal("1")),
        )
        # Check that balances() method on individual ClientTransactions
        self.assertEqual(
            hook_args.client_transactions[
                f"{self.client_id}_{self.client_transaction_id_custom}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(0), debit=Decimal(10), net=Decimal("-10")),
        )
        self.assertEqual(
            hook_args.client_transactions[
                f"{self.client_id}_{self.client_transaction_id_settle}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0)),
        )
        self.assertEqual(
            hook_args.client_transactions[
                f"{self.client_id}_{self.client_transaction_id_settle}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(0), net=Decimal("20")),
        )
        self.assertEqual(
            hook_args.client_transactions[
                f"{self.client_id}_{self.client_transaction_id_transfer}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="HKK",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(1), debit=Decimal(0), net=Decimal("1")),
        )

    def test_pre_posting_hook_raises_with_naive_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            PrePostingHookArguments(
                effective_datetime=self.test_naive_datetime,
                posting_instructions=[],
                client_transactions={},
            )
        expected = "'effective_datetime' of PrePostingHookArguments is not timezone aware."
        self.assertEquals(expected, str(ex.exception))

    def test_pre_posting_hook_raises_with_non_utc_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            PrePostingHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
                posting_instructions=[],
                client_transactions={},
            )
        expected = "'effective_datetime' of PrePostingHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    def test_pre_posting_hook_spec(self):
        hook_args = PrePostingHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            posting_instructions=[],
            client_transactions={},
        )
        spec = hook_args._spec(language_code=symbols.Languages.ENGLISH)  # noqa: SLF001
        public_attributes_dict = {
            attribute.name: attribute
            for attribute in hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001
        }

        self.assertEquals(spec.name, "PrePostingHookArguments")
        self.assertEquals(spec.public_attributes.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.constructor.args.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.public_methods, {})

        public_attributes = spec.public_attributes

        self.assertEquals(len(public_attributes), 3)
        effective_datetime, posting_instructions, client_transactions = public_attributes.values()

        self.assertEquals(effective_datetime.name, "effective_datetime")
        self.assertEquals(effective_datetime.type, "datetime")

        self.assertEquals(posting_instructions.name, "posting_instructions")
        self.assertEquals(posting_instructions.type, _PITypes_str)

        self.assertEquals(client_transactions.name, "client_transactions")
        self.assertEquals(client_transactions.type, "Dict[str, ClientTransaction]")

    # SupervisorPrePostingCodeArguments

    def test_supervisor_pre_posting_hook_arguments_attributes_can_be_set(self):
        custom_ctx = ClientTransaction(
            client_transaction_id=self.client_transaction_id_custom,
            account_id=self.account_id,
            posting_instructions=[self.custom_instruction],
            tside=Tside.LIABILITY,
        )
        settle_ctx = ClientTransaction(
            client_transaction_id=self.client_transaction_id_settle,
            account_id=self.account_id,
            posting_instructions=[self.inbound_auth, self.settlement],
            tside=Tside.LIABILITY,
        )
        transfer_ctx = ClientTransaction(
            client_transaction_id=self.client_transaction_id_transfer,
            account_id=self.account_id,
            posting_instructions=[self.transfer],
            tside=Tside.LIABILITY,
        )
        hard_settle_ctx = ClientTransaction(
            client_transaction_id="123",
            account_id="123",
            posting_instructions=[self.hard_settle],
            tside=Tside.ASSET,
        )
        hook_args = SupervisorPrePostingHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            supervisee_posting_instructions={
                self.account_id: [self.custom_instruction, self.settlement, self.transfer],
                "123": [self.hard_settle],
            },
            supervisee_client_transactions={
                self.account_id: {
                    f"{self.client_id}_{self.client_transaction_id_custom}": custom_ctx,
                    f"{self.client_id}_{self.client_transaction_id_settle}": settle_ctx,
                    f"{self.client_id}_{self.client_transaction_id_transfer}": transfer_ctx,
                },
                "123": {
                    f"{self.client_id}_123": hard_settle_ctx,
                },
            },
        )
        self.assertEquals(hook_args.effective_datetime, self.test_zoned_datetime_utc)
        self.assertEquals(
            hook_args.supervisee_posting_instructions,
            {
                self.account_id: [self.custom_instruction, self.settlement, self.transfer],
                "123": [self.hard_settle],
            },
        )
        self.assertEqual(
            hook_args.supervisee_client_transactions,
            {
                self.account_id: {
                    f"{self.client_id}_{self.client_transaction_id_custom}": custom_ctx,
                    f"{self.client_id}_{self.client_transaction_id_settle}": settle_ctx,
                    f"{self.client_id}_{self.client_transaction_id_transfer}": transfer_ctx,
                },
                "123": {
                    f"{self.client_id}_123": hard_settle_ctx,
                },
            },
        )
        # Check that balances() method on individual PIs for each supervisee
        self.assertEqual(
            hook_args.supervisee_posting_instructions[self.account_id][0].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(0), debit=Decimal(10), net=Decimal("-10")),
        )
        self.assertEqual(
            hook_args.supervisee_posting_instructions[self.account_id][1].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(0), net=Decimal("20")),
        )
        self.assertEqual(
            hook_args.supervisee_posting_instructions[self.account_id][1].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                )
            ],
            Balance(credit=Decimal(0), debit=Decimal(20), net=Decimal("-20")),
        )
        self.assertEqual(
            hook_args.supervisee_posting_instructions[self.account_id][2].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="HKK",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(1), debit=Decimal(0), net=Decimal("1")),
        )
        self.assertEqual(
            hook_args.supervisee_posting_instructions["123"][0].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(0), net=Decimal("-20")),
        )
        # Check that balances() method on individual ClientTransactions
        self.assertEqual(
            hook_args.supervisee_client_transactions[self.account_id][
                f"{self.client_id}_{self.client_transaction_id_custom}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(0), debit=Decimal(10), net=Decimal("-10")),
        )
        self.assertEqual(
            hook_args.supervisee_client_transactions[self.account_id][
                f"{self.client_id}_{self.client_transaction_id_settle}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0)),
        )
        self.assertEqual(
            hook_args.supervisee_client_transactions[self.account_id][
                f"{self.client_id}_{self.client_transaction_id_settle}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(0), net=Decimal("20")),
        )
        self.assertEqual(
            hook_args.supervisee_client_transactions[self.account_id][
                f"{self.client_id}_{self.client_transaction_id_transfer}"
            ].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="HKK",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(1), debit=Decimal(0), net=Decimal("1")),
        )
        self.assertEqual(
            hook_args.supervisee_client_transactions["123"][f"{self.client_id}_123"].balances()[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
            Balance(credit=Decimal(20), debit=Decimal(0), net=Decimal("-20")),
        )

    def test_supervisor_pre_posting_hook_raises_with_naive_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorPrePostingHookArguments(
                effective_datetime=self.test_naive_datetime,
                supervisee_posting_instructions={},
                supervisee_client_transactions={},
            )
        expected = (
            "'effective_datetime' of SupervisorPrePostingHookArguments is not timezone aware."
        )
        self.assertEquals(expected, str(ex.exception))

    def test_supervisor_pre_posting_hook_raises_with_non_utc_effective_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorPrePostingHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
                supervisee_posting_instructions={},
                supervisee_client_transactions={},
            )
        expected = "'effective_datetime' of SupervisorPrePostingHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    def test_supervisor_pre_posting_hook_spec(self):
        hook_args = SupervisorPrePostingHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            supervisee_posting_instructions={},
            supervisee_client_transactions={},
        )
        spec = hook_args._spec(language_code=symbols.Languages.ENGLISH)  # noqa: SLF001
        public_attributes_dict = {
            attribute.name: attribute
            for attribute in hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001
        }

        self.assertEquals(spec.name, "SupervisorPrePostingHookArguments")
        self.assertEquals(spec.public_attributes.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.constructor.args.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.public_methods, {})

        public_attributes = spec.public_attributes

        self.assertEquals(len(public_attributes), 3)
        effective_datetime, postings, client_transactions = public_attributes.values()

        self.assertEquals(effective_datetime.name, "effective_datetime")
        self.assertEquals(effective_datetime.type, "datetime")

        self.assertEquals(postings.name, "supervisee_posting_instructions")
        self.assertEquals(postings.type, f"Dict[str, {_PITypes_str}]")

        self.assertEquals(client_transactions.name, "supervisee_client_transactions")
        self.assertEquals(client_transactions.type, "Dict[str, Dict[str, ClientTransaction]]")

    # PreParameterChangeHookArguments

    def test_pre_parameter_change_hook_arguments_attributes_can_be_set(self):
        parameters = {"parameter1": "value1"}
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            updated_parameter_values=parameters,
        )
        self.assertEquals(hook_args.effective_datetime, self.test_zoned_datetime_utc)
        self.assertEquals(hook_args.updated_parameter_values, parameters)

    def test_pre_parameter_change_hook_raises_with_naive_effective_datetime(self):
        parameters = {"parameter1": "value1"}
        with self.assertRaises(InvalidSmartContractError) as ex:
            PreParameterChangeHookArguments(
                effective_datetime=self.test_naive_datetime,
                updated_parameter_values=parameters,
            )
        expected = "'effective_datetime' of PreParameterChangeHookArguments is not timezone aware."
        self.assertEquals(expected, str(ex.exception))

    def test_pre_parameter_change_hook_raises_with_non_utc_effective_datetime(self):
        parameters = {"parameter1": "value1"}
        with self.assertRaises(InvalidSmartContractError) as ex:
            PreParameterChangeHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
                updated_parameter_values=parameters,
            )
        expected = "'effective_datetime' of PreParameterChangeHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    def test_only_set_pre_parameter_change_hook_arguments_attributes_can_be_accessed(self):
        parameters = {"parameter1": "value1"}
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            updated_parameter_values=parameters,
        )
        self.assertEquals(
            hook_args.__dict__,
            {
                "effective_datetime": self.test_zoned_datetime_utc,
                "updated_parameter_values": parameters,
            },
        )

    def test_pre_parameter_change_hook_arguments_attributes_not_set_cant_be_accessed(self):
        parameters = {"parameter1": "value1"}
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            updated_parameter_values=parameters,
        )
        self.assertRaises(AttributeError, getattr, hook_args, "old_parameter_values")

    def test_pre_parameter_change_hook_spec(self):
        parameters = {"parameter1": "value1"}
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            updated_parameter_values=parameters,
        )
        spec = hook_args._spec(language_code=symbols.Languages.ENGLISH)  # noqa: SLF001
        public_attributes_dict = {
            attribute.name: attribute
            for attribute in hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001
        }

        self.assertEquals(spec.name, "PreParameterChangeHookArguments")
        self.assertEquals(spec.public_attributes.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.constructor.args.keys(), public_attributes_dict.keys())
        self.assertEquals(spec.public_methods, {})

    def test_pre_parameter_change_hook_arguments_public_attributes(self):
        parameters = {"parameter1": "value1"}
        hook_args = PreParameterChangeHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            updated_parameter_values=parameters,
        )
        public_attributes = hook_args._public_attributes(  # noqa: SLF001
            language_code=symbols.Languages.ENGLISH
        )

        self.assertEquals(len(public_attributes), 2)
        effective_datetime_attr, parameters_attr = public_attributes

        self.assertEquals(effective_datetime_attr.name, "effective_datetime")
        self.assertEquals(effective_datetime_attr.type, "datetime")

        self.assertEquals(parameters_attr.name, "updated_parameter_values")
        self.assertEquals(
            parameters_attr.type,
            "Dict[str, Union[Decimal, str, datetime, OptionalValue, UnionItemValue, int]",
        )

    # ScheduledEventHookArguments

    def test_scheduled_event_hook_arguments_attributes_can_be_set(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        hook_args = ScheduledEventHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            event_type=event_type,
            pause_at_datetime=pause_at_datetime,
        )
        self.assertEqual(hook_args.effective_datetime, self.test_zoned_datetime_utc)
        self.assertEqual(hook_args.event_type, event_type)
        self.assertEqual(hook_args.pause_at_datetime, pause_at_datetime)

    def test_scheduled_event_hook_arguments_raises_with_naive_effective_datetime(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        with self.assertRaises(InvalidSmartContractError) as ex:
            ScheduledEventHookArguments(
                effective_datetime=self.test_naive_datetime,
                event_type=event_type,
                pause_at_datetime=pause_at_datetime,
            )
        expected = "'effective_datetime' of ScheduledEventHookArguments is not timezone aware."
        self.assertEquals(expected, str(ex.exception))

    def test_scheduled_event_hook_arguments_raises_with_non_utc_effective_datetime(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        with self.assertRaises(InvalidSmartContractError) as ex:
            ScheduledEventHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
                event_type=event_type,
                pause_at_datetime=pause_at_datetime,
            )
        expected = "'effective_datetime' of ScheduledEventHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    def test_scheduled_event_hook_arguments_raises_with_naive_pause_at_datetime(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12)
        with self.assertRaises(InvalidSmartContractError) as ex:
            ScheduledEventHookArguments(
                effective_datetime=self.test_zoned_datetime_utc,
                event_type=event_type,
                pause_at_datetime=pause_at_datetime,
            )
        expected = "'pause_at_datetime' of ScheduledEventHookArguments is not timezone aware."
        self.assertEquals(expected, str(ex.exception))

    def test_scheduled_event_hook_arguments_raises_with_non_utc_pause_at_datetime(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("US/Pacific"))
        with self.assertRaises(InvalidSmartContractError) as ex:
            ScheduledEventHookArguments(
                effective_datetime=self.test_zoned_datetime_utc,
                event_type=event_type,
                pause_at_datetime=pause_at_datetime,
            )
        expected = "'pause_at_datetime' of ScheduledEventHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    def test_scheduled_event_hook_arguments_raises_with_incorrect_pause_at_datetime_type(self):
        event_type = "test_event"
        with self.assertRaises(StrongTypingError) as ex:
            ScheduledEventHookArguments(
                effective_datetime=self.test_zoned_datetime_utc,
                event_type=event_type,
                pause_at_datetime=False,
            )
        expected = "'pause_at_datetime' expected datetime, got 'False' of type bool"  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    def test_only_set_scheduled_event_hook_arguments_attributes_can_be_accessed(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        hook_args = ScheduledEventHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            event_type=event_type,
            pause_at_datetime=pause_at_datetime,
        )
        self.assertEqual(
            hook_args.__dict__,
            {
                "effective_datetime": self.test_zoned_datetime_utc,
                "event_type": event_type,
                "pause_at_datetime": pause_at_datetime,
            },
        )

    def test_scheduled_event_hook_arguments_attributes_not_set_cant_be_accessed(self):
        event_type = "test_event"
        hook_args = ScheduledEventHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            event_type=event_type,
        )
        self.assertRaises(AttributeError, getattr, hook_args, "old_parameter_values")

    def test_scheduled_event_hook_spec(self):
        event_type = "test_event"
        hook_args = ScheduledEventHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            event_type=event_type,
            pause_at_datetime=datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC")),
        )
        spec = hook_args._spec(language_code=symbols.Languages.ENGLISH)  # noqa: SLF001
        public_attributes_dict = {
            attribute.name: attribute
            for attribute in hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001
        }

        self.assertEqual(spec.name, "ScheduledEventHookArguments")
        self.assertEqual(spec.public_attributes.keys(), public_attributes_dict.keys())
        self.assertEqual(spec.constructor.args.keys(), public_attributes_dict.keys())
        self.assertEqual(spec.public_methods, {})

    def test_scheduled_event_hook_arguments_public_attributes(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        hook_args = ScheduledEventHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            event_type=event_type,
            pause_at_datetime=pause_at_datetime,
        )
        public_attributes = hook_args._public_attributes(  # noqa: SLF001
            language_code=symbols.Languages.ENGLISH
        )

        self.assertEqual(len(public_attributes), 3)
        effective_datetime_attr, event_type_attr, scheduled_job_attr = public_attributes

        self.assertEqual(effective_datetime_attr.name, "effective_datetime")
        self.assertEqual(effective_datetime_attr.type, "datetime")

        self.assertEqual(event_type_attr.name, "event_type")
        self.assertEqual(event_type_attr.type, "str")

        self.assertEqual(scheduled_job_attr.name, "pause_at_datetime")
        self.assertEqual(scheduled_job_attr.type, "Optional[datetime]")

    # SupervisorScheduledEventHookArguments

    def test_supervisor_scheduled_event_hook_arguments_attributes_can_be_set(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        supervisee_pause_at_datetime = {"supervisee_account_id": pause_at_datetime}
        hook_args = SupervisorScheduledEventHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            event_type=event_type,
            supervisee_pause_at_datetime=supervisee_pause_at_datetime,
            pause_at_datetime=pause_at_datetime,
        )
        self.assertEqual(hook_args.effective_datetime, self.test_zoned_datetime_utc)
        self.assertEqual(hook_args.event_type, event_type)
        self.assertEqual(
            hook_args.pause_at_datetime, datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        )
        self.assertEqual(hook_args.supervisee_pause_at_datetime, supervisee_pause_at_datetime)

    def test_supervisor_scheduled_event_hook_arguments_raises_with_naive_effective_datetime(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorScheduledEventHookArguments(
                effective_datetime=self.test_naive_datetime,
                event_type=event_type,
                pause_at_datetime=pause_at_datetime,
                supervisee_pause_at_datetime={},
            )
        expected = (
            "'effective_datetime' of SupervisorScheduledEventHookArguments is not timezone aware."
        )
        self.assertEquals(expected, str(ex.exception))

    def test_supervisor_scheduled_event_hook_arguments_raises_with_non_datetime_pause_at_datetime(
        self,
    ):
        event_type = "test_event"
        with self.assertRaises(StrongTypingError) as ex:
            SupervisorScheduledEventHookArguments(
                effective_datetime=self.test_zoned_datetime_utc,
                event_type=event_type,
                pause_at_datetime=False,
                supervisee_pause_at_datetime={},
            )
        expected = "'pause_at_datetime' expected datetime, got 'False' of type bool"
        self.assertEquals(expected, str(ex.exception))

    def test_supervisor_scheduled_eventhook_arguments_raises_with_non_utc_effective_datetime(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorScheduledEventHookArguments(
                effective_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
                event_type=event_type,
                pause_at_datetime=pause_at_datetime,
                supervisee_pause_at_datetime={},
            )
        expected = "'effective_datetime' of SupervisorScheduledEventHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    def test_supervisor_scheduled_event_hook_arguments_raises_with_naive_pause_at_datetime(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12)
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorScheduledEventHookArguments(
                effective_datetime=self.test_zoned_datetime_utc,
                event_type=event_type,
                pause_at_datetime=pause_at_datetime,
                supervisee_pause_at_datetime={},
            )
        expected = (
            "'pause_at_datetime' of SupervisorScheduledEventHookArguments is not timezone aware."
        )
        self.assertEquals(expected, str(ex.exception))

    def test_supervisor_scheduled_event_hook_arguments_raises_with_non_utc_pause_at_datetime(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("US/Pacific"))
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorScheduledEventHookArguments(
                effective_datetime=self.test_zoned_datetime_utc,
                event_type=event_type,
                pause_at_datetime=pause_at_datetime,
                supervisee_pause_at_datetime={},
            )
        expected = "'pause_at_datetime' of SupervisorScheduledEventHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    def test_scheduled_event_hook_arguments_raises_with_naive_supervisee_pause_at_datetime(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        naive_pause_at_datetime = datetime(2022, 10, 12)
        supervisee_pause_at_datetime = {
            "supervisee_account_id": pause_at_datetime,
            "supervisee_account_id_naive": naive_pause_at_datetime,
        }
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorScheduledEventHookArguments(
                effective_datetime=self.test_zoned_datetime_utc,
                event_type=event_type,
                pause_at_datetime=pause_at_datetime,
                supervisee_pause_at_datetime=supervisee_pause_at_datetime,
            )
        expected = "'supervisee_pause_at_datetime['supervisee_account_id_naive']' of SupervisorScheduledEventHookArguments is not timezone aware."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    def test_scheduled_event_hook_arguments_raises_with_incorrect_supervisee_pause_at_datetime_type(
        self,
    ):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        not_a_datetime = False
        supervisee_pause_at_datetime = {
            "supervisee_account_id": pause_at_datetime,
            "supervisee_account_id_wrong_type": not_a_datetime,
        }
        with self.assertRaises(StrongTypingError) as ex:
            SupervisorScheduledEventHookArguments(
                effective_datetime=self.test_zoned_datetime_utc,
                event_type=event_type,
                pause_at_datetime=pause_at_datetime,
                supervisee_pause_at_datetime=supervisee_pause_at_datetime,
            )
        expected = "'supervisee_pause_at_datetime['supervisee_account_id_wrong_type']' expected datetime, got 'False' of type bool"  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    def test_scheduled_event_hook_arguments_raises_with_non_utc_supervisee_pause_at_datetime(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        non_utc_pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("US/Pacific"))
        supervisee_pause_at_datetime = {
            "supervisee_account_id": pause_at_datetime,
            "supervisee_account_id_naive": non_utc_pause_at_datetime,
        }
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorScheduledEventHookArguments(
                effective_datetime=self.test_zoned_datetime_utc,
                event_type=event_type,
                pause_at_datetime=pause_at_datetime,
                supervisee_pause_at_datetime=supervisee_pause_at_datetime,
            )
        expected = "'supervisee_pause_at_datetime['supervisee_account_id_naive']' of SupervisorScheduledEventHookArguments must have timezone UTC, currently US/Pacific."  # noqa: E501
        self.assertEquals(expected, str(ex.exception))

    def test_only_set_supervisor_scheduled_event_hook_arguments_attributes_can_be_accessed(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        supervisee_pause_at_datetime = {"supervisee_account_id": pause_at_datetime}
        hook_args = SupervisorScheduledEventHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            event_type=event_type,
            supervisee_pause_at_datetime=supervisee_pause_at_datetime,
            pause_at_datetime=pause_at_datetime,
        )
        self.assertEqual(
            hook_args.__dict__,
            {
                "effective_datetime": self.test_zoned_datetime_utc,
                "event_type": event_type,
                "supervisee_pause_at_datetime": supervisee_pause_at_datetime,
                "pause_at_datetime": pause_at_datetime,
            },
        )

    def test_supervisor_scheduled_event_hook_arguments_attributes_not_set_cant_be_accessed(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        supervisee_pause_at_datetime = {"supervisee_account_id": pause_at_datetime}
        hook_args = SupervisorScheduledEventHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            event_type=event_type,
            supervisee_pause_at_datetime=supervisee_pause_at_datetime,
            pause_at_datetime=pause_at_datetime,
        )
        self.assertRaises(AttributeError, getattr, hook_args, "old_parameter_values")

    def test_supervisor_scheduled_event_hook_spec(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        supervisee_pause_at_datetime = {"supervisee_account_id": pause_at_datetime}
        hook_args = SupervisorScheduledEventHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            event_type=event_type,
            supervisee_pause_at_datetime=supervisee_pause_at_datetime,
            pause_at_datetime=pause_at_datetime,
        )
        spec = hook_args._spec(language_code=symbols.Languages.ENGLISH)  # noqa: SLF001
        public_attributes_dict = {
            attribute.name: attribute
            for attribute in hook_args._public_attributes(symbols.Languages.ENGLISH)  # noqa: SLF001
        }

        self.assertEqual(spec.name, "SupervisorScheduledEventHookArguments")
        self.assertEqual(spec.public_attributes.keys(), public_attributes_dict.keys())
        self.assertEqual(spec.constructor.args.keys(), public_attributes_dict.keys())
        self.assertEqual(spec.public_methods, {})

    def test_supervisor_scheduled_event_hook_arguments_public_attributes(self):
        event_type = "test_event"
        pause_at_datetime = datetime(2022, 10, 12, tzinfo=ZoneInfo("UTC"))
        supervisee_pause_at_datetime = {"supervisee_account_id": pause_at_datetime}
        hook_args = SupervisorScheduledEventHookArguments(
            effective_datetime=self.test_zoned_datetime_utc,
            event_type=event_type,
            supervisee_pause_at_datetime=supervisee_pause_at_datetime,
            pause_at_datetime=pause_at_datetime,
        )
        public_attributes = hook_args._public_attributes(  # noqa: SLF001
            language_code=symbols.Languages.ENGLISH
        )

        self.assertEqual(len(public_attributes), 4)
        (
            effective_datetime_attr,
            event_type_attr,
            pause_at_datetime_attr,
            supervisee_pause_at_datetime_attr,
        ) = public_attributes

        self.assertEqual(effective_datetime_attr.name, "effective_datetime")
        self.assertEqual(effective_datetime_attr.type, "datetime")

        self.assertEqual(event_type_attr.name, "event_type")
        self.assertEqual(event_type_attr.type, "str")

        self.assertEqual(supervisee_pause_at_datetime_attr.name, "supervisee_pause_at_datetime")
        self.assertEqual(supervisee_pause_at_datetime_attr.type, "Dict[str, Optional[datetime]]")

        self.assertEqual(pause_at_datetime_attr.name, "pause_at_datetime")
        self.assertEqual(pause_at_datetime_attr.type, "Optional[datetime]")

    # PlanNotificationDirective

    def test_plan_notification_directive(self):
        notification_type = "test_notification_type"
        notification_details = {"key1": "value1"}
        plan_notification_directive = PlanNotificationDirective(
            notification_type=notification_type,
            notification_details=notification_details,
        )
        self.assertEqual(notification_type, plan_notification_directive.notification_type)
        self.assertEqual(notification_details, plan_notification_directive.notification_details)

    def test_plan_notification_directive_missing_details_raises(self):
        notification_type = "test_notification_type"
        notification_details = {}
        with self.assertRaises(InvalidSmartContractError) as ex:
            PlanNotificationDirective(
                notification_type=notification_type,
                notification_details=notification_details,
            )
        expected = "PlanNotificationDirective 'notification_details' must be populated"
        self.assertEquals(expected, str(ex.exception))

    # AccountNotificationDirective

    def test_account_notification_directive_missing_details_raises(self):
        notification_type = "test_notification_type"
        notification_details = {}
        with self.assertRaises(InvalidSmartContractError) as ex:
            AccountNotificationDirective(
                notification_type=notification_type,
                notification_details=notification_details,
            )
        expected = "AccountNotificationDirective 'notification_details' must be populated"
        self.assertEquals(expected, str(ex.exception))

    # ScheduleSkip

    def test_schedule_skip_with_end_datetime(self):
        skip_schedule = ScheduleSkip(
            end=datetime(year=2021, month=12, day=31, tzinfo=ZoneInfo("UTC"))
        )
        self.assertEqual(
            skip_schedule.end, datetime(year=2021, month=12, day=31, tzinfo=ZoneInfo("UTC"))
        )

    def test_schedule_skip_raises_with_end_datetime_not_provided(self):
        with self.assertRaises(TypeError) as ex:
            ScheduleSkip()
        self.assertEqual(
            "ScheduleSkip.__init__() missing 1 required keyword-only argument: 'end'",
            str(ex.exception),
        )

    def test_schedule_skip_raises_with_end_datetime_none(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            ScheduleSkip(end=None)
        self.assertIn("ScheduleSkip 'end' must be populated", str(ex.exception))

    def test_schedule_skip_raises_with_end_datetime_invalid(self):
        with self.assertRaises(StrongTypingError) as ex:
            ScheduleSkip(end=False)
        self.assertEqual("Expected datetime, got 'False' of type bool", str(ex.exception))

    # AuthorisedAmount

    def test_authorised_amount_both_arguments_not_set(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            AdjustmentAmount()
        self.assertEqual(
            "Either amount or replacement amount argument must be set, not both.", str(ex.exception)
        )

    def test_authorised_amount_both_arguments_set(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            AdjustmentAmount(amount=Decimal(1), replacement_amount=Decimal(2))
        self.assertEqual(
            "Either amount or replacement amount argument must be set, not both.", str(ex.exception)
        )

    def test_authorised_amount_init(self):
        auth_amount = AdjustmentAmount(amount=Decimal(-10))
        self.assertEqual(auth_amount.amount, Decimal(-10))
        self.assertEqual(auth_amount.replacement_amount, None)
        auth_amount = AdjustmentAmount(replacement_amount=Decimal(1))
        self.assertEqual(auth_amount.amount, None)
        self.assertEqual(auth_amount.replacement_amount, Decimal(1))

    def test_authorised_amount_skips_validation_with_from_proto(self):
        auth_amount = AdjustmentAmount(
            amount=Decimal(-10), replacement_amount=Decimal(1), _from_proto=True
        )
        self.assertEqual(auth_amount.amount, Decimal(-10))
        self.assertEqual(auth_amount.replacement_amount, Decimal(1))

    # PostingInstructions

    # OutboundAuthorisation

    def test_outbound_auth_posting_instruction_raises_with_missing_attributes(self):
        with self.assertRaises(TypeError) as ex:
            OutboundAuthorisation(amount=Decimal(10))
        self.assertEqual(
            "Authorisation.__init__() missing 4 required keyword-only arguments: "
            "'client_transaction_id', 'denomination', 'target_account_id', and "
            "'internal_account_id'",
            str(ex.exception),
        )

    def test_outbound_auth_posting_instruction_all_attributes(self):
        pi_datetime = datetime(2002, 2, 2, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        transaction_code = TransactionCode(domain="A", family="B", subfamily="C")
        pi = OutboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            advice=True,
            override_all_restrictions=True,
            transaction_code=transaction_code,
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=pi_datetime,
            value_datetime=pi_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_instruction_id",
        )
        # Direct attributes
        self.assertEqual("xx", pi.client_transaction_id)
        self.assertEqual(self.test_account_id, pi.target_account_id)
        self.assertEqual("1", pi.internal_account_id)
        self.assertEqual(Decimal(10), pi.amount)
        self.assertEqual("GBP", pi.denomination)
        self.assertEqual(True, pi.advice)
        self.assertEqual(True, pi.override_all_restrictions)
        self.assertEqual(transaction_code, pi.transaction_code)
        self.assertEqual("test", pi.instruction_details["testy"])
        # Indirect attributes
        self.assertEqual(pi_datetime, pi.value_datetime)
        self.assertEqual(pi_datetime, pi.insertion_datetime)
        self.assertEqual("instruction_id", pi.id)
        self.assertEqual("batch_id", pi.batch_id)
        self.assertEqual("CoreContracts_instruction_id", pi.unique_client_transaction_id)
        self.assertEqual("client_batch_id", pi.client_batch_id)
        # Private attributes (to be used in balances calculation)
        self.assertEqual(pi_committed_postings[0], pi._committed_postings[0])  # noqa: SLF001

    def test_outbound_auth_posting_instruction_default_attributes_no_output_attrs(self):
        pi = OutboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        # Direct attributes
        self.assertEqual("xx", pi.client_transaction_id)
        self.assertEqual(self.test_account_id, pi.target_account_id)
        self.assertEqual("1", pi.internal_account_id)
        self.assertEqual(Decimal(10), pi.amount)
        self.assertEqual("GBP", pi.denomination)
        self.assertEqual(False, pi.advice)
        self.assertEqual(False, pi.override_all_restrictions)
        self.assertIsNone(pi.transaction_code)
        self.assertEqual({}, pi.instruction_details)
        # Indirect attributes
        self.assertIsNone(pi.insertion_datetime)
        self.assertIsNone(pi.id)
        self.assertIsNone(pi.value_datetime)
        self.assertIsNone(pi.batch_id)
        self.assertIsNone(pi.unique_client_transaction_id)
        self.assertIsNone(pi.client_batch_id)
        # Private attribute used in balances calculation
        self.assertIsNone(pi._committed_postings)  # noqa: SLF001

    def test_outbound_auth_posting_instruction_skip_type_checking(self):
        pi = OutboundAuthorisation(
            client_transaction_id=1,
            target_account_id=1,
            internal_account_id=1,
            amount=1,
            denomination=1,
            advice=1,
            transaction_code=1,
            instruction_details=1,
            override_all_restrictions=1,
            _from_proto=True,
        )
        # Direct attributes
        self.assertEqual(1, pi.client_transaction_id)
        self.assertEqual(1, pi.target_account_id)
        self.assertEqual(1, pi.internal_account_id)
        self.assertEqual(1, pi.amount)
        self.assertEqual(1, pi.denomination)
        self.assertEqual(1, pi.advice)
        self.assertEqual(1, pi.override_all_restrictions)
        self.assertEqual(1, pi.transaction_code)
        self.assertEqual(1, pi.instruction_details)

    def test_outbound_auth_posting_instruction_raises_with_invalid_instruction_details_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            OutboundAuthorisation(
                client_transaction_id="xx",
                target_account_id=self.test_account_id,
                internal_account_id="1",
                amount=Decimal(10),
                denomination="GBP",
                instruction_details=123,
            )

        self.assertIn(
            "'OutboundAuthorisation.instruction_details' expected Dict[str, str] if populated, "
            "got '123' of type int",
            str(ex.exception),
        )

    def test_outbound_auth_posting_instruction_raises_with_invalid_transaction_code_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            OutboundAuthorisation(
                client_transaction_id="xx",
                target_account_id=self.test_account_id,
                internal_account_id="1",
                amount=Decimal(10),
                denomination="GBP",
                transaction_code=123,
            )

        self.assertIn(
            "'OutboundAuthorisation.transaction_code' expected TransactionCode if populated, got "
            "'123' of type int",
            str(ex.exception),
        )

    def test_outbound_auth_instruction_balances_errors_if_own_account_id_not_provided(self):
        pi = OutboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "An account_id must be specified for the balances calculation.",
        ):
            pi.balances()

    def test_outbound_auth_instruction_balances_errors_if_committed_postings_not_provided(self):
        pi = OutboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        pi._set_output_attributes(own_account_id=self.test_account_id)  # noqa: SLF001
        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "The OutboundAuthorisation posting instruction type does not support the balances "
            "method for the non-historical data as committed_postings are not available.",
        ):
            pi.balances()

    def test_outbound_auth_instruction_balances_errors_if_tside_not_provided(self):
        pi = OutboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=[
                Posting(
                    account_id=self.test_account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=False,
                    phase=Phase.PENDING_OUT,
                    amount=Decimal(10),
                    denomination="GBP",
                ),
            ],
        )
        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "A tside must be specified for the balances calculation.",
        ):
            pi.balances()

    def test_outbound_auth_instruction_balances_for_both_tsides(self):
        pi = OutboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.ASSET,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(10),
                ),
            },
            balances,
        )

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.LIABILITY,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(-10),
                ),
            },
            balances,
        )

    def test_outbound_auth_instruction_balances_for_both_tsides_in_balances_args(self):
        pi = OutboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
        )

        balances = pi.balances(tside=Tside.ASSET)
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(10),
                ),
            },
            balances,
        )

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
        )

        balances = pi.balances(tside=Tside.LIABILITY)
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(-10),
                ),
            },
            balances,
        )

    def test_balances_method_filters_on_own_account_id(self):
        pi = OutboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
            Posting(
                account_id="filter-out-this-account-pls",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_OUT,
                amount=Decimal(1984),
                denomination="GBP",
            ),
        ]

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.ASSET,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(10),
                ),
            },
            balances,
        )

    def test_balances_method_filters_on_account_id_in_balances_arg(self):
        pi = OutboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
            Posting(
                account_id="filter-out-this-account-pls",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_OUT,
                amount=Decimal(1984),
                denomination="GBP",
            ),
        ]

        pi._set_output_attributes(  # noqa: SLF001
            committed_postings=committed_postings,
            tside=Tside.ASSET,
        )

        balances = pi.balances(account_id=self.test_account_id)
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(10),
                ),
            },
            balances,
        )

    def test_balances_method_filters_account_id_in_balances_arg_not_own_account_id(self):
        pi = OutboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
            Posting(
                account_id="filter-out-this-account-pls",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_OUT,
                amount=Decimal(1984),
                denomination="GBP",
            ),
        ]

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id="filter-out-this-account-pls",
            committed_postings=committed_postings,
            tside=Tside.ASSET,
        )

        balances = pi.balances(account_id=self.test_account_id)
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(10),
                ),
            },
            balances,
        )

    def test_balances_method_returns_zero_default_dict_for_non_existing_balance_key(self):
        pi = OutboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            )
        ]

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.ASSET,
        )

        balances = pi.balances()
        self.assertEqual(
            Balance(
                credit=Decimal(0),
                debit=Decimal(0),
                net=Decimal(0),
            ),
            balances[
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
        )
        self.assertEqual(
            Balance(
                credit=Decimal(0),
                debit=Decimal(10),
                net=Decimal(10),
            ),
            balances[
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                )
            ],
        )

    # InboundAuthorisation

    def test_inbound_auth_posting_instruction_raises_with_missing_attributes(self):
        with self.assertRaises(TypeError) as ex:
            InboundAuthorisation(amount=Decimal(10))
        self.assertEqual(
            "Authorisation.__init__() missing 4 required keyword-only arguments: "
            "'client_transaction_id', 'denomination', 'target_account_id', and "
            "'internal_account_id'",
            str(ex.exception),
        )

    def test_inbound_auth_posting_instruction_all_attributes(self):
        pi_datetime = datetime(2002, 2, 2, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        transaction_code = TransactionCode(domain="A", family="B", subfamily="C")
        pi = InboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            advice=True,
            override_all_restrictions=True,
            transaction_code=transaction_code,
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=pi_datetime,
            value_datetime=pi_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_instruction_id",
        )
        # Direct attributes
        self.assertEqual("xx", pi.client_transaction_id)
        self.assertEqual(self.test_account_id, pi.target_account_id)
        self.assertEqual("1", pi.internal_account_id)
        self.assertEqual(Decimal(10), pi.amount)
        self.assertEqual("GBP", pi.denomination)
        self.assertEqual(True, pi.advice)
        self.assertEqual(True, pi.override_all_restrictions)
        self.assertEqual(transaction_code, pi.transaction_code)
        self.assertEqual("test", pi.instruction_details["testy"])
        # Indirect attributes
        self.assertEqual(pi_datetime, pi.value_datetime)
        self.assertEqual(pi_datetime, pi.insertion_datetime)
        self.assertEqual("instruction_id", pi.id)
        self.assertEqual("batch_id", pi.batch_id)
        self.assertEqual("CoreContracts_instruction_id", pi.unique_client_transaction_id)
        self.assertEqual("client_batch_id", pi.client_batch_id)
        # Private attributes (to be used in balances calculation)
        self.assertEqual(pi_committed_postings[0], pi._committed_postings[0])  # noqa: SLF001

    def test_inbound_auth_posting_instruction_default_attributes_no_output_attrs(self):
        pi = InboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        # Direct attributes
        self.assertEqual("xx", pi.client_transaction_id)
        self.assertEqual(self.test_account_id, pi.target_account_id)
        self.assertEqual("1", pi.internal_account_id)
        self.assertEqual(Decimal(10), pi.amount)
        self.assertEqual("GBP", pi.denomination)
        self.assertEqual(False, pi.advice)
        self.assertEqual(False, pi.override_all_restrictions)
        self.assertIsNone(pi.transaction_code)
        self.assertEqual({}, pi.instruction_details)
        # Indirect attributes
        self.assertIsNone(pi.insertion_datetime)
        self.assertIsNone(pi.id)
        self.assertIsNone(pi.value_datetime)
        self.assertIsNone(pi.batch_id)
        self.assertIsNone(pi.unique_client_transaction_id)
        self.assertIsNone(pi.client_batch_id)
        # Private attribute - used for balances calc.
        self.assertIsNone(pi._committed_postings)  # noqa: SLF001

    def test_inbound_auth_posting_instruction_skip_type_checking(self):
        pi = InboundAuthorisation(
            client_transaction_id=1,
            target_account_id=1,
            internal_account_id=1,
            amount=1,
            denomination=1,
            advice=1,
            transaction_code=1,
            instruction_details=1,
            override_all_restrictions=1,
            _from_proto=True,
        )
        # Direct attributes
        self.assertEqual(1, pi.client_transaction_id)
        self.assertEqual(1, pi.target_account_id)
        self.assertEqual(1, pi.internal_account_id)
        self.assertEqual(1, pi.amount)
        self.assertEqual(1, pi.denomination)
        self.assertEqual(1, pi.advice)
        self.assertEqual(1, pi.override_all_restrictions)
        self.assertEqual(1, pi.transaction_code)
        self.assertEqual(1, pi.instruction_details)

    def test_inbound_auth_posting_instruction_raises_with_invalid_instruction_details_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            InboundAuthorisation(
                client_transaction_id="xx",
                target_account_id=self.test_account_id,
                internal_account_id="1",
                amount=Decimal(10),
                denomination="GBP",
                instruction_details=123,
            )

        self.assertIn(
            "'InboundAuthorisation.instruction_details' expected Dict[str, str] if populated, got "
            "'123' of type int",
            str(ex.exception),
        )

    def test_inbound_auth_posting_instruction_raises_with_invalid_transaction_code_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            InboundAuthorisation(
                client_transaction_id="xx",
                target_account_id=self.test_account_id,
                internal_account_id="1",
                amount=Decimal(10),
                denomination="GBP",
                transaction_code=123,
            )

        self.assertIn(
            "'InboundAuthorisation.transaction_code' expected TransactionCode if populated, got "
            "'123' of type int",
            str(ex.exception),
        )

    def test_inbound_auth_instruction_balances_errors_if_own_account_id_not_provided(self):
        pi = InboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "An account_id must be specified for the balances calculation.",
        ):
            pi.balances()

    def test_inbound_auth_instruction_balances_errors_if_committed_postings_not_provided(self):
        pi = InboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        pi._set_output_attributes(own_account_id=self.test_account_id)  # noqa: SLF001
        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "The InboundAuthorisation posting instruction type does not support the balances "
            "method for the non-historical data as committed_postings are not available.",
        ):
            pi.balances()

    def test_inbound_auth_instruction_balances_for_both_tsides(self):
        pi = InboundAuthorisation(
            client_transaction_id="xx",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_IN,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.ASSET,
        )

        balances = pi.balances()
        self.assertDictEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                ): Balance(
                    credit=Decimal(10),
                    debit=Decimal(0),
                    net=Decimal(-10),
                ),
            },
            balances,
        )

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.LIABILITY,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                ): Balance(
                    credit=Decimal(10),
                    debit=Decimal(0),
                    net=Decimal(10),
                ),
            },
            balances,
        )

    # AuthAdjustment

    def test_auth_adjust_posting_instruction_raises_with_missing_attributes(self):
        with self.assertRaises(TypeError) as ex:
            AuthorisationAdjustment()
        self.assertEqual(
            "AuthorisationAdjustment.__init__() missing 2 required keyword-only arguments: "
            "'client_transaction_id' and 'adjustment_amount'",
            str(ex.exception),
        )

    def test_auth_adjust_posting_instruction_raises_with_adjustment_amount_not_populated(self):
        with self.assertRaises(StrongTypingError) as ex:
            AuthorisationAdjustment(
                client_transaction_id="xx",
                adjustment_amount=None,
                advice=True,
                override_all_restrictions=True,
            )
        self.assertEqual(
            "AuthorisationAdjustment 'adjustment_amount' must be populated",
            str(ex.exception),
        )

    def test_auth_adjust_posting_instruction_raises_with_adjustment_amount_invalid_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            AuthorisationAdjustment(
                client_transaction_id="xx",
                adjustment_amount=234,
                advice=True,
                override_all_restrictions=True,
            )
        self.assertEqual(
            "'AuthorisationAdjustment.adjustment_amount' expected AdjustmentAmount, got '234' of "
            "type int",
            str(ex.exception),
        )

    def test_auth_adjust_posting_instruction_all_attributes(self):
        pi_datetime = datetime(2002, 2, 2, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        transaction_code = TransactionCode(domain="A", family="B", subfamily="C")
        adjustment_amount = AdjustmentAmount(amount=Decimal(10))
        pi = AuthorisationAdjustment(
            client_transaction_id="xx",
            adjustment_amount=adjustment_amount,
            advice=True,
            override_all_restrictions=True,
            transaction_code=transaction_code,
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=pi_datetime,
            value_datetime=pi_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_instruction_id",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            authorised_amount=Decimal(110),
            delta_amount=Decimal(10),
            denomination="GBP",
        )
        # Direct attributes
        self.assertEqual("xx", pi.client_transaction_id)
        self.assertTrue(pi.advice)
        self.assertEqual(adjustment_amount, pi.adjustment_amount)
        self.assertEqual(True, pi.override_all_restrictions)
        self.assertEqual(transaction_code, pi.transaction_code)
        self.assertEqual("test", pi.instruction_details["testy"])
        # Indirect attributes
        self.assertEqual(pi_datetime, pi.value_datetime)
        self.assertEqual(pi_datetime, pi.insertion_datetime)
        self.assertEqual("instruction_id", pi.id)
        self.assertEqual("batch_id", pi.batch_id)
        self.assertEqual("CoreContracts_instruction_id", pi.unique_client_transaction_id)
        self.assertEqual("client_batch_id", pi.client_batch_id)
        self.assertEqual(self.test_account_id, pi.target_account_id)
        self.assertEqual("1", pi.internal_account_id)
        self.assertEqual(Decimal(110), pi.authorised_amount)
        self.assertEqual(Decimal(10), pi.delta_amount)
        self.assertEqual("GBP", pi.denomination)
        # Private attributes (to be used in balances calculation)
        self.assertEqual(pi_committed_postings[0], pi._committed_postings[0])  # noqa: SLF001

    def test_auth_adjust_posting_instruction_default_attributes_no_output_attrs(self):
        adjustment_amount = AdjustmentAmount(replacement_amount=Decimal(50))
        pi = AuthorisationAdjustment(
            client_transaction_id="xx", adjustment_amount=adjustment_amount
        )
        # Direct attributes
        self.assertEqual("xx", pi.client_transaction_id)
        self.assertFalse(pi.advice)
        self.assertEqual(adjustment_amount, pi.adjustment_amount)
        self.assertEqual(False, pi.override_all_restrictions)
        self.assertIsNone(pi.transaction_code)
        self.assertEqual({}, pi.instruction_details)
        # Indirect attributes
        self.assertIsNone(pi.insertion_datetime)
        self.assertIsNone(pi.id)
        self.assertIsNone(pi.value_datetime)
        self.assertIsNone(pi.batch_id)
        self.assertIsNone(pi.unique_client_transaction_id)
        self.assertIsNone(pi.client_batch_id)
        self.assertIsNone(pi._committed_postings)  # noqa: SLF001
        # Release specific output attributes
        self.assertIsNone(pi.authorised_amount)
        self.assertIsNone(pi.delta_amount)
        self.assertIsNone(pi.denomination)
        self.assertIsNone(pi.target_account_id)
        self.assertIsNone(pi.internal_account_id)

    def test_auth_adjust_posting_instruction_skip_type_checking(self):
        pi = AuthorisationAdjustment(
            client_transaction_id=1,
            adjustment_amount=1,
            advice=1,
            transaction_code=1,
            instruction_details=1,
            override_all_restrictions=1,
            _from_proto=True,
        )
        # Direct attributes
        self.assertEqual(1, pi.client_transaction_id)
        self.assertEqual(1, pi.advice)
        self.assertEqual(1, pi.adjustment_amount)
        self.assertEqual(1, pi.override_all_restrictions)
        self.assertEqual(1, pi.transaction_code)
        self.assertEqual(1, pi.instruction_details)

    def test_auth_adjust_posting_instruction_raises_with_invalid_instruction_details_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            AuthorisationAdjustment(
                client_transaction_id="xx",
                adjustment_amount=AdjustmentAmount(amount=Decimal(10)),
                advice=True,
                override_all_restrictions=True,
                transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
                instruction_details=123,
            )

        self.assertIn(
            "'AuthorisationAdjustment.instruction_details' expected Dict[str, str] if populated, "
            "got '123' of type int",
            str(ex.exception),
        )

    def test_auth_adjust_posting_instruction_raises_with_invalid_transaction_code_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            AuthorisationAdjustment(
                client_transaction_id="xx",
                adjustment_amount=AdjustmentAmount(amount=Decimal(10)),
                advice=True,
                override_all_restrictions=True,
                transaction_code=123,
            )

        self.assertIn(
            "'AuthorisationAdjustment.transaction_code' expected TransactionCode if populated, "
            "got '123' of type int",
            str(ex.exception),
        )

    def test_auth_adjust_instruction_balances_errors_if_own_account_id_not_provided(self):
        pi = AuthorisationAdjustment(
            client_transaction_id="xx",
            adjustment_amount=AdjustmentAmount(amount=Decimal(10)),
            advice=True,
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )

        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "An account_id must be specified for the balances calculation.",
        ):
            pi.balances()

    def test_auth_adjust_instruction_balances_errors_if_committed_postings_not_provided(self):
        pi = AuthorisationAdjustment(
            client_transaction_id="xx",
            adjustment_amount=AdjustmentAmount(amount=Decimal(10)),
            advice=True,
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(own_account_id=self.test_account_id)  # noqa: SLF001
        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "The AuthorisationAdjustment posting instruction type does not support the balances "
            "method for the non-historical data as committed_postings are not available.",
        ):
            pi.balances()

    def test_auth_adjust_instruction_balances_for_both_tsides(self):
        pi = AuthorisationAdjustment(
            client_transaction_id="xx",
            adjustment_amount=AdjustmentAmount(amount=Decimal(10)),
            advice=True,
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_IN,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.ASSET,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                ): Balance(
                    credit=Decimal(10),
                    debit=Decimal(0),
                    net=Decimal(-10),
                ),
            },
            balances,
        )

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.LIABILITY,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                ): Balance(
                    credit=Decimal(10),
                    debit=Decimal(0),
                    net=Decimal(10),
                ),
            },
            balances,
        )

    def test_auth_adjust_instruction_zero_amount(self):
        pi = AuthorisationAdjustment(
            client_transaction_id="xx",
            adjustment_amount=AdjustmentAmount(amount=Decimal(0)),
        )
        # Amount is zero not None
        self.assertEqual(pi.adjustment_amount.amount, Decimal("0"))
        self.assertIsNone(pi.adjustment_amount.replacement_amount)
        self.assertIsNone(pi.authorised_amount)
        self.assertIsNone(pi.delta_amount)

    def test_auth_adjust_instruction_zero_replacement_amount(self):
        pi = AuthorisationAdjustment(
            client_transaction_id="xx",
            adjustment_amount=AdjustmentAmount(replacement_amount=Decimal(0)),
        )
        # Replacement amount is zero not None
        self.assertIsNone(pi.adjustment_amount.amount)
        self.assertEqual(pi.adjustment_amount.replacement_amount, Decimal("0"))
        self.assertIsNone(pi.authorised_amount)
        self.assertIsNone(pi.delta_amount)

    def test_auth_adjust_instruction_zero_authorised_amount(self):
        pi = AuthorisationAdjustment(
            client_transaction_id="xx",
            adjustment_amount=AdjustmentAmount(amount=Decimal(0)),
        )
        pi._set_output_attributes(  # noqa: SLF001
            authorised_amount=Decimal("0"),
        )
        # Authorised amount is zero not None
        self.assertEqual(pi.adjustment_amount.amount, Decimal("0"))
        self.assertIsNone(pi.adjustment_amount.replacement_amount)
        self.assertEqual(pi.authorised_amount, Decimal("0"))
        self.assertIsNone(pi.delta_amount)

    def test_auth_adjust_instruction_zero_delta_amount(self):
        pi = AuthorisationAdjustment(
            client_transaction_id="xx",
            adjustment_amount=AdjustmentAmount(amount=Decimal(0)),
        )
        pi._set_output_attributes(  # noqa: SLF001
            delta_amount=Decimal("0"),
        )
        # Delta amount is zero not None
        self.assertEqual(pi.adjustment_amount.amount, Decimal("0"))
        self.assertIsNone(pi.adjustment_amount.replacement_amount)
        self.assertIsNone(pi.authorised_amount)
        self.assertEqual(pi.delta_amount, Decimal("0"))

    # Settlement

    def test_settlement_posting_instruction_raises_with_missing_attributes(self):
        with self.assertRaises(TypeError) as ex:
            Settlement()
        self.assertEqual(
            "Settlement.__init__() missing 1 required keyword-only argument: "
            "'client_transaction_id'",
            str(ex.exception),
        )

    def test_settlement_posting_instruction_all_attributes(self):
        pi_datetime = datetime(2002, 2, 2, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        transaction_code = TransactionCode(domain="A", family="B", subfamily="C")
        pi = Settlement(
            client_transaction_id="xx",
            final=True,
            amount=Decimal(10),
            override_all_restrictions=True,
            transaction_code=transaction_code,
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=pi_datetime,
            value_datetime=pi_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_instruction_id",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            denomination="GBP",
        )
        # Direct attributes
        self.assertEqual("xx", pi.client_transaction_id)
        self.assertTrue(pi.final)
        self.assertEqual(Decimal(10), pi.amount)
        self.assertEqual(True, pi.override_all_restrictions)
        self.assertEqual(transaction_code, pi.transaction_code)
        self.assertEqual("test", pi.instruction_details["testy"])
        # Indirect attributes
        self.assertEqual(pi_datetime, pi.value_datetime)
        self.assertEqual(pi_datetime, pi.insertion_datetime)
        self.assertEqual("instruction_id", pi.id)
        self.assertEqual("batch_id", pi.batch_id)
        self.assertEqual("CoreContracts_instruction_id", pi.unique_client_transaction_id)
        self.assertEqual("client_batch_id", pi.client_batch_id)
        self.assertEqual(self.test_account_id, pi.target_account_id)
        self.assertEqual("1", pi.internal_account_id)
        self.assertEqual("GBP", pi.denomination)
        # Private attributes (to be used in balances calculation)
        self.assertEqual(pi_committed_postings[0], pi._committed_postings[0])  # noqa: SLF001

    def test_settlement_posting_instruction_default_attributes_no_output_attrs(self):
        pi = Settlement(client_transaction_id="xx")
        # Direct attributes
        self.assertEqual("xx", pi.client_transaction_id)
        self.assertFalse(pi.final)
        self.assertIsNone(pi.amount)
        self.assertEqual(False, pi.override_all_restrictions)
        self.assertIsNone(pi.transaction_code)
        self.assertEqual({}, pi.instruction_details)
        # Indirect attributes
        self.assertIsNone(pi.insertion_datetime)
        self.assertIsNone(pi.id)
        self.assertIsNone(pi.value_datetime)
        self.assertIsNone(pi.batch_id)
        self.assertIsNone(pi.unique_client_transaction_id)
        self.assertIsNone(pi.client_batch_id)
        self.assertIsNone(pi._committed_postings)  # noqa: SLF001
        # Release specific output attributes
        self.assertIsNone(pi.denomination)
        self.assertIsNone(pi.target_account_id)
        self.assertIsNone(pi.internal_account_id)

    def test_settlement_posting_instruction_skip_type_checking(self):
        pi = Settlement(
            client_transaction_id=1,
            amount=1,
            final=1,
            transaction_code=1,
            instruction_details=1,
            override_all_restrictions=1,
            _from_proto=True,
        )
        # Direct attributes
        self.assertEqual(1, pi.client_transaction_id)
        self.assertEqual(1, pi.final)
        self.assertEqual(1, pi.amount)
        self.assertEqual(1, pi.override_all_restrictions)
        self.assertEqual(1, pi.transaction_code)
        self.assertEqual(1, pi.instruction_details)

    def test_settlement_posting_instruction_raises_with_invalid_instruction_details_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            Settlement(
                client_transaction_id="xx",
                final=True,
                amount=Decimal(10),
                override_all_restrictions=True,
                transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
                instruction_details=123,
            )

        self.assertIn(
            "'Settlement.instruction_details' expected Dict[str, str] if populated, got '123' of "
            "type int",
            str(ex.exception),
        )

    def test_settlement_posting_instruction_raises_with_invalid_transaction_code_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            Settlement(
                client_transaction_id="xx",
                final=True,
                amount=Decimal(10),
                override_all_restrictions=True,
                transaction_code=123,
            )

        self.assertIn(
            "'Settlement.transaction_code' expected TransactionCode if populated, got '123' of "
            "type int",
            str(ex.exception),
        )

    def test_settlement_posting_instruction_balances_errors_if_own_account_id_not_provided(self):
        pi = Settlement(
            client_transaction_id="xx",
            final=True,
            amount=Decimal(10),
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )

        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "An account_id must be specified for the balances calculation.",
        ):
            pi.balances()

    def test_settlement_posting_instruction_balances_errors_if_committed_postings_not_provided(
        self,
    ):
        pi = Settlement(
            client_transaction_id="xx",
            final=True,
            amount=Decimal(10),
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(own_account_id=self.test_account_id)  # noqa: SLF001

        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "The Settlement posting instruction type does not support the balances "
            "method for the non-historical data as committed_postings are not available.",
        ):
            pi.balances()

    def test_settlement_posting_instruction_balances_for_both_tsides(self):
        pi = Settlement(
            client_transaction_id="xx",
            final=True,
            amount=Decimal(10),
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.ASSET,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                ): Balance(
                    credit=Decimal(10),
                    debit=Decimal(0),
                    net=Decimal(-10),
                ),
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(10),
                ),
            },
            balances,
        )

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.LIABILITY,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                ): Balance(
                    credit=Decimal(10),
                    debit=Decimal(0),
                    net=Decimal(10),
                ),
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(-10),
                ),
            },
            balances,
        )

    # Release

    def test_release_posting_instruction_raises_with_missing_attributes(self):
        with self.assertRaises(TypeError) as ex:
            Release()
        self.assertEqual(
            "Release.__init__() missing 1 required keyword-only argument: 'client_transaction_id'",
            str(ex.exception),
        )

    def test_release_posting_instruction_all_attributes(self):
        pi_datetime = datetime(2002, 2, 2, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        transaction_code = TransactionCode(domain="A", family="B", subfamily="C")
        pi = Release(
            client_transaction_id="xx",
            override_all_restrictions=True,
            transaction_code=transaction_code,
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=pi_datetime,
            value_datetime=pi_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_instruction_id",
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        # Direct attributes
        self.assertEqual("xx", pi.client_transaction_id)
        self.assertEqual(True, pi.override_all_restrictions)
        self.assertEqual(transaction_code, pi.transaction_code)
        self.assertEqual("test", pi.instruction_details["testy"])
        # Indirect attributes
        self.assertEqual(pi_datetime, pi.value_datetime)
        self.assertEqual(pi_datetime, pi.insertion_datetime)
        self.assertEqual("instruction_id", pi.id)
        self.assertEqual("batch_id", pi.batch_id)
        self.assertEqual("CoreContracts_instruction_id", pi.unique_client_transaction_id)
        self.assertEqual("client_batch_id", pi.client_batch_id)
        self.assertEqual(self.test_account_id, pi.target_account_id)
        self.assertEqual("1", pi.internal_account_id)
        self.assertEqual(Decimal(10), pi.amount)
        self.assertEqual("GBP", pi.denomination)
        # Private attributes (to be used in balances calculation)
        self.assertEqual(pi_committed_postings[0], pi._committed_postings[0])  # noqa: SLF001

    def test_release_posting_instruction_default_attributes_no_output_attrs(self):
        pi = Release(
            client_transaction_id="xx",
        )
        # Direct attributes
        self.assertEqual("xx", pi.client_transaction_id)
        self.assertEqual(False, pi.override_all_restrictions)
        self.assertIsNone(pi.transaction_code)
        self.assertEqual({}, pi.instruction_details)
        # Indirect attributes
        self.assertIsNone(pi.insertion_datetime)
        self.assertIsNone(pi.id)
        self.assertIsNone(pi.value_datetime)
        self.assertIsNone(pi.batch_id)
        self.assertIsNone(pi.unique_client_transaction_id)
        self.assertIsNone(pi.client_batch_id)
        self.assertIsNone(pi._committed_postings)  # noqa: SLF001
        # Release specific output attributes
        self.assertIsNone(pi.amount)
        self.assertIsNone(pi.denomination)
        self.assertIsNone(pi.target_account_id)
        self.assertIsNone(pi.internal_account_id)

    def test_release_posting_instruction_skip_type_checking(self):
        pi = Release(
            client_transaction_id=1,
            transaction_code=1,
            instruction_details=1,
            override_all_restrictions=1,
            _from_proto=True,
        )
        # Direct attributes
        self.assertEqual(1, pi.client_transaction_id)
        self.assertEqual(1, pi.override_all_restrictions)
        self.assertEqual(1, pi.transaction_code)
        self.assertEqual(1, pi.instruction_details)

    def test_release_posting_instruction_raises_with_invalid_instruction_details_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            Release(
                client_transaction_id="xx",
                override_all_restrictions=True,
                transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
                instruction_details=123,
            )

        self.assertIn(
            "'Release.instruction_details' expected Dict[str, str] if populated, got '123' of "
            "type int",
            str(ex.exception),
        )

    def test_release_posting_instruction_raises_with_invalid_transaction_code_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            Release(
                client_transaction_id="xx", override_all_restrictions=True, transaction_code=123
            )

        self.assertIn(
            "'Release.transaction_code' expected TransactionCode if populated, got '123' of type "
            "int",
            str(ex.exception),
        )

    # SupervisorConversionHookResult

    def test_supervisor_conversion_hook_result(self):
        scheduled_events_return_value = {
            "event_1": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(1970, 1, 1, second=2, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(
                    year="2000",
                    month="1",
                    day="1",
                    hour="0",
                    minute="0",
                    second="0",
                ),
                skip=ScheduleSkip(
                    end=datetime(1970, 1, 1, second=3, tzinfo=ZoneInfo("UTC")),
                ),
            ),
            "event_2": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=5, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(1970, 1, 1, second=6, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(
                    day_of_week="mon",
                ),
            ),
        }
        supervisor_conversion_hook_result = SupervisorConversionHookResult(
            scheduled_events_return_value=scheduled_events_return_value
        )
        self.assertEqual(
            scheduled_events_return_value,
            supervisor_conversion_hook_result.scheduled_events_return_value,
        )

    def test_supervisor_conversion_hook_result_no_events(self):
        supervisor_conversion_hook_result = SupervisorConversionHookResult()
        self.assertEqual({}, supervisor_conversion_hook_result.scheduled_events_return_value)

    def test_release_posting_instruction_balances_errors_if_own_account_id_not_provided(self):
        pi = Release(
            client_transaction_id="xx",
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )

        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "An account_id must be specified for the balances calculation.",
        ):
            pi.balances()

    def test_release_posting_instruction_balances_errors_if_committed_postings_not_provided(self):
        pi = Release(
            client_transaction_id="xx",
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(own_account_id=self.test_account_id)  # noqa: SLF001

        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "The Release posting instruction type does not support the balances "
            "method for the non-historical data as committed_postings are not available.",
        ):
            pi.balances()

    def test_release_posting_instruction_balances_for_both_tsides(self):
        pi = Release(
            client_transaction_id="xx",
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.ASSET,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                ): Balance(
                    credit=Decimal(10),
                    debit=Decimal(0),
                    net=Decimal(-10),
                ),
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(10),
                ),
            },
            balances,
        )

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.LIABILITY,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_OUT,
                ): Balance(
                    credit=Decimal(10),
                    debit=Decimal(0),
                    net=Decimal(10),
                ),
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(-10),
                ),
            },
            balances,
        )

    # CustomInstruction

    def test_custom_instruction_raises_with_missing_attributes(self):
        with self.assertRaises(TypeError) as ex:
            CustomInstruction()
        self.assertEqual(
            "CustomInstruction.__init__() missing 1 required keyword-only argument: 'postings'",
            str(ex.exception),
        )

    def test_custom_instruction_all_attributes(self):
        pi_datetime = datetime(2002, 2, 2, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        transaction_code = TransactionCode(domain="A", family="B", subfamily="C")
        pi = CustomInstruction(
            postings=pi_committed_postings,
            override_all_restrictions=True,
            transaction_code=transaction_code,
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=pi_datetime,
            value_datetime=pi_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_instruction_id",
        )
        # Direct attributes
        self.assertEqual(pi_committed_postings[0], pi.postings[0])
        self.assertEqual(True, pi.override_all_restrictions)
        self.assertEqual(transaction_code, pi.transaction_code)
        self.assertEqual("test", pi.instruction_details["testy"])
        # Indirect attributes
        self.assertEqual(pi_datetime, pi.value_datetime)
        self.assertEqual(pi_datetime, pi.insertion_datetime)
        self.assertEqual("instruction_id", pi.id)
        self.assertEqual("batch_id", pi.batch_id)
        self.assertEqual("CoreContracts_instruction_id", pi.unique_client_transaction_id)
        self.assertEqual("client_batch_id", pi.client_batch_id)
        # Private attributes (to be used in balances calculation)
        self.assertEqual(pi_committed_postings[0], pi._committed_postings[0])  # noqa: SLF001

    def test_custom_instruction_default_attributes_no_output_attrs(self):
        pi_committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        pi = CustomInstruction(postings=pi_committed_postings)
        # Direct attributes
        self.assertEqual(pi_committed_postings[0], pi.postings[0])
        self.assertEqual(False, pi.override_all_restrictions)
        self.assertIsNone(pi.transaction_code)
        self.assertEqual({}, pi.instruction_details)
        # Indirect attributes
        self.assertIsNone(pi.insertion_datetime)
        self.assertIsNone(pi.id)
        self.assertIsNone(pi.value_datetime)
        self.assertIsNone(pi.batch_id)
        self.assertIsNone(pi.unique_client_transaction_id)
        self.assertIsNone(pi.client_batch_id)
        # This is set to the postings for the CustomInstructions
        self.assertEqual(pi_committed_postings[0], pi._committed_postings[0])  # noqa: SLF001

    def test_custom_instruction_skip_type_checking(self):
        pi = CustomInstruction(
            postings=1,
            transaction_code=1,
            instruction_details=1,
            override_all_restrictions=1,
            _from_proto=True,
        )
        # Direct attributes
        self.assertEqual(1, pi.postings)
        self.assertEqual(1, pi.override_all_restrictions)
        self.assertEqual(1, pi.transaction_code)
        self.assertEqual(1, pi.instruction_details)

    def test_custom_instruction_skips_validation(self):
        # This raises no error with invalid attributes when _from_proto=True.
        custom_instruction = CustomInstruction(postings=1, _from_proto=True)
        self.assertEqual(1, custom_instruction.postings)

    def test_custom_instruction_raises_with_postings_not_provided(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            CustomInstruction(postings=None)

        self.assertIn(
            "'postings' must be a non empty list, got None",
            str(ex.exception),
        )

    def test_custom_instruction_raises_with_empty_postings(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            CustomInstruction(postings=[])

        self.assertIn(
            "'postings' must be a non empty list, got []",
            str(ex.exception),
        )

    def test_custom_instruction_raises_with_postings_invalid_element_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            CustomInstruction(postings=[1])

        self.assertIn(
            "Expected List[Posting], got '1'",
            str(ex.exception),
        )

    def test_custom_instruction_raises_with_postings_element_being_none(self):
        with self.assertRaises(StrongTypingError) as ex:
            CustomInstruction(postings=[None])

        self.assertIn(
            "Expected List[Posting], got None",
            str(ex.exception),
        )

    def test_custom_instruction_raises_with_invalid_transaction_code(self):
        with self.assertRaises(StrongTypingError) as ex:
            CustomInstruction(
                postings=[
                    Posting(
                        account_id=self.test_account_id,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        credit=False,
                        phase=Phase.PENDING_OUT,
                        amount=Decimal(10),
                        denomination="GBP",
                    )
                ],
                transaction_code=123,
            )

        self.assertIn(
            "'CustomInstruction.transaction_code' expected TransactionCode if populated, got "
            "'123' of type int",
            str(ex.exception),
        )

    def test_custom_instruction_raises_with_invalid_instruction_details(self):
        with self.assertRaises(StrongTypingError) as ex:
            CustomInstruction(
                postings=[
                    Posting(
                        account_id=self.test_account_id,
                        account_address=DEFAULT_ADDRESS,
                        asset=DEFAULT_ASSET,
                        credit=False,
                        phase=Phase.PENDING_OUT,
                        amount=Decimal(10),
                        denomination="GBP",
                    )
                ],
                instruction_details=123,
            )

        self.assertIn(
            "'CustomInstruction.instruction_details' expected Dict[str, str] if populated, got "
            "'123' of type int",
            str(ex.exception),
        )

    def test_custom_instruction_balances_errors_if_own_account_id_not_provided(self):
        pi = CustomInstruction(
            postings=[
                Posting(
                    account_id=self.test_account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=False,
                    phase=Phase.PENDING_OUT,
                    amount=Decimal(10),
                    denomination="GBP",
                ),
            ],
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )

        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "An account_id must be specified for the balances calculation.",
        ):
            pi.balances()

    def test_custom_instruction_default_balances_returned_if_committed_postings_not_provided(self):
        pi = CustomInstruction(
            postings=[
                Posting(
                    account_id=self.test_account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=False,
                    phase=Phase.PENDING_OUT,
                    amount=Decimal(10),
                    denomination="GBP",
                ),
            ],
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id, tside=Tside.ASSET
        )
        pi._committed_postings = []  # noqa: SLF001

        balances = pi.balances()
        self.assertEqual(
            {},
            balances,
        )

    def test_custom_instruction_balances_for_both_tsides(self):
        pi = CustomInstruction(
            postings=[
                Posting(
                    account_id=self.test_account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=True,
                    phase=Phase.PENDING_IN,
                    amount=Decimal(10),
                    denomination="GBP",
                ),
            ],
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            tside=Tside.ASSET,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                ): Balance(
                    credit=Decimal(10),
                    debit=Decimal(0),
                    net=Decimal(-10),
                ),
            },
            balances,
        )

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            tside=Tside.LIABILITY,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                ): Balance(
                    credit=Decimal(10),
                    debit=Decimal(0),
                    net=Decimal(10),
                ),
            },
            balances,
        )

    def test_custom_instruction_aggregated_balances(self):
        pi = CustomInstruction(
            postings=[
                Posting(
                    account_id=self.test_account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=True,
                    phase=Phase.PENDING_IN,
                    amount=Decimal(10),
                    denomination="GBP",
                ),
                Posting(
                    account_id=self.test_account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=True,
                    phase=Phase.PENDING_IN,
                    amount=Decimal(15),
                    denomination="GBP",
                ),
            ],
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            tside=Tside.ASSET,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                ): Balance(
                    credit=Decimal(25),
                    debit=Decimal(0),
                    net=Decimal(-25),
                ),
            },
            balances,
        )

    # InboundHardSettlement

    def test_inbound_settle_posting_instruction_raises_with_missing_attributes(self):
        with self.assertRaises(TypeError) as ex:
            InboundHardSettlement()
        self.assertEqual(
            "HardSettlement.__init__() missing 4 required keyword-only arguments: 'amount', "
            "'denomination', 'target_account_id', and 'internal_account_id'",
            str(ex.exception),
        )

    def test_inbound_settle_posting_instruction_all_attributes(self):
        pi_datetime = datetime(2002, 2, 2, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        transaction_code = TransactionCode(domain="A", family="B", subfamily="C")
        pi = InboundHardSettlement(
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            advice=True,
            override_all_restrictions=True,
            transaction_code=transaction_code,
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=pi_datetime,
            value_datetime=pi_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_instruction_id",
        )
        # Direct attributes
        self.assertEqual(self.test_account_id, pi.target_account_id)
        self.assertEqual("1", pi.internal_account_id)
        self.assertEqual(Decimal(10), pi.amount)
        self.assertEqual("GBP", pi.denomination)
        self.assertEqual(True, pi.advice)
        self.assertEqual(True, pi.override_all_restrictions)
        self.assertEqual(transaction_code, pi.transaction_code)
        self.assertEqual("test", pi.instruction_details["testy"])
        # Indirect attributes
        self.assertEqual(pi_datetime, pi.value_datetime)
        self.assertEqual(pi_datetime, pi.insertion_datetime)
        self.assertEqual("instruction_id", pi.id)
        self.assertEqual("batch_id", pi.batch_id)
        self.assertEqual("CoreContracts_instruction_id", pi.unique_client_transaction_id)
        self.assertEqual("client_batch_id", pi.client_batch_id)
        # Private attributes (to be used in balances calculation)
        self.assertEqual(pi_committed_postings[0], pi._committed_postings[0])  # noqa: SLF001

    def test_inbound_settle_posting_instruction_default_attributes_no_output_attrs(self):
        pi = InboundHardSettlement(
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        # Direct attributes
        self.assertEqual(self.test_account_id, pi.target_account_id)
        self.assertEqual("1", pi.internal_account_id)
        self.assertEqual(Decimal(10), pi.amount)
        self.assertEqual("GBP", pi.denomination)
        self.assertEqual(False, pi.advice)
        self.assertEqual(False, pi.override_all_restrictions)
        self.assertIsNone(pi.transaction_code)
        self.assertEqual({}, pi.instruction_details)
        # Indirect attributes
        self.assertIsNone(pi.insertion_datetime)
        self.assertIsNone(pi.id)
        self.assertIsNone(pi.value_datetime)
        self.assertIsNone(pi.batch_id)
        self.assertIsNone(pi.unique_client_transaction_id)
        self.assertIsNone(pi.client_batch_id)
        # Private attribute used in balances calculation
        self.assertIsNone(pi._committed_postings)  # noqa: SLF001

    def test_inbound_settle_posting_instruction_skip_type_checking(self):
        pi = InboundHardSettlement(
            target_account_id=1,
            internal_account_id=1,
            amount=1,
            denomination=1,
            advice=1,
            transaction_code=1,
            instruction_details=1,
            override_all_restrictions=1,
            _from_proto=True,
        )
        # Direct attributes
        self.assertEqual(1, pi.target_account_id)
        self.assertEqual(1, pi.internal_account_id)
        self.assertEqual(1, pi.amount)
        self.assertEqual(1, pi.denomination)
        self.assertEqual(1, pi.advice)
        self.assertEqual(1, pi.override_all_restrictions)
        self.assertEqual(1, pi.transaction_code)
        self.assertEqual(1, pi.instruction_details)

    def test_inbound_settle_posting_instruction_balances_errors_if_own_account_id_not_provided(
        self,
    ):
        pi = InboundHardSettlement(
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            advice=True,
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )

        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "An account_id must be specified for the balances calculation.",
        ):
            pi.balances()

    def test_inbound_settle_posting_instruction_balances_errors_if_committed_postings_not_provided(
        self,
    ):
        pi = InboundHardSettlement(
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            advice=True,
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(own_account_id=self.test_account_id)  # noqa: SLF001

        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "The InboundHardSettlement posting instruction type does not support the balances "
            "method for the non-historical data as committed_postings are not available.",
        ):
            pi.balances()

    def test_inbound_settle_posting_instruction_balances_for_both_tsides(self):
        pi = InboundHardSettlement(
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            advice=True,
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            tside=Tside.LIABILITY,
            committed_postings=committed_postings,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                ): Balance(
                    credit=Decimal(10),
                    debit=Decimal(0),
                    net=Decimal(10),
                ),
            },
            balances,
        )

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.ASSET,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                ): Balance(
                    credit=Decimal(10),
                    debit=Decimal(0),
                    net=Decimal(-10),
                ),
            },
            balances,
        )

    # OutboundHardSettlement

    def test_outbound_settle_posting_instruction_raises_with_missing_attributes(self):
        with self.assertRaises(TypeError) as ex:
            OutboundHardSettlement()
        self.assertEqual(
            "HardSettlement.__init__() missing 4 required keyword-only arguments: 'amount', "
            "'denomination', 'target_account_id', and 'internal_account_id'",
            str(ex.exception),
        )

    def test_outbound_settle_posting_instruction_all_attributes(self):
        pi_datetime = datetime(2002, 2, 2, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        transaction_code = TransactionCode(domain="A", family="B", subfamily="C")
        pi = OutboundHardSettlement(
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            advice=True,
            override_all_restrictions=True,
            transaction_code=transaction_code,
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=pi_datetime,
            value_datetime=pi_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_instruction_id",
        )
        # Direct attributes
        self.assertEqual(self.test_account_id, pi.target_account_id)
        self.assertEqual("1", pi.internal_account_id)
        self.assertEqual(Decimal(10), pi.amount)
        self.assertEqual("GBP", pi.denomination)
        self.assertEqual(True, pi.advice)
        self.assertEqual(True, pi.override_all_restrictions)
        self.assertEqual(transaction_code, pi.transaction_code)
        self.assertEqual("test", pi.instruction_details["testy"])
        # Indirect attributes
        self.assertEqual(pi_datetime, pi.value_datetime)
        self.assertEqual(pi_datetime, pi.insertion_datetime)
        self.assertEqual("instruction_id", pi.id)
        self.assertEqual("batch_id", pi.batch_id)
        self.assertEqual("CoreContracts_instruction_id", pi.unique_client_transaction_id)
        self.assertEqual("client_batch_id", pi.client_batch_id)
        # Private attributes (to be used in balances calculation)
        self.assertEqual(pi_committed_postings[0], pi._committed_postings[0])  # noqa: SLF001

    def test_outbound_settle_posting_instruction_default_attributes_no_output_attrs(self):
        pi = OutboundHardSettlement(
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        # Direct attributes
        self.assertEqual(self.test_account_id, pi.target_account_id)
        self.assertEqual("1", pi.internal_account_id)
        self.assertEqual(Decimal(10), pi.amount)
        self.assertEqual("GBP", pi.denomination)
        self.assertEqual(False, pi.advice)
        self.assertEqual(False, pi.override_all_restrictions)
        self.assertIsNone(pi.transaction_code)
        self.assertEqual({}, pi.instruction_details)
        # Indirect attributes
        self.assertIsNone(pi.insertion_datetime)
        self.assertIsNone(pi.id)
        self.assertIsNone(pi.value_datetime)
        self.assertIsNone(pi.batch_id)
        self.assertIsNone(pi.unique_client_transaction_id)
        self.assertIsNone(pi.client_batch_id)
        # Private attribute used in balances calculation
        self.assertIsNone(pi._committed_postings)  # noqa: SLF001

    def test_outbound_settle_posting_instruction_skip_type_checking(self):
        pi = OutboundHardSettlement(
            target_account_id=1,
            internal_account_id=1,
            amount=1,
            denomination=1,
            advice=1,
            transaction_code=1,
            instruction_details=1,
            override_all_restrictions=1,
            _from_proto=True,
        )
        # Direct attributes
        self.assertEqual(1, pi.target_account_id)
        self.assertEqual(1, pi.internal_account_id)
        self.assertEqual(1, pi.amount)
        self.assertEqual(1, pi.denomination)
        self.assertEqual(1, pi.advice)
        self.assertEqual(1, pi.override_all_restrictions)
        self.assertEqual(1, pi.transaction_code)
        self.assertEqual(1, pi.instruction_details)

    def test_outbound_settle_posting_instruction_balances_errors_if_own_account_id_not_provided(
        self,
    ):
        pi = OutboundHardSettlement(
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            advice=True,
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )

        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "An account_id must be specified for the balances calculation.",
        ):
            pi.balances()

    def test_outbound_settle_posting_instruction_balances_errors_if_committed_postings_not_provided(
        self,
    ):
        pi = OutboundHardSettlement(
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            advice=True,
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(own_account_id=self.test_account_id)  # noqa: SLF001

        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "The OutboundHardSettlement posting instruction type does not support the balances "
            "method for the non-historical data as committed_postings are not available.",
        ):
            pi.balances()

    def test_outbound_settle_posting_instruction_balances_for_both_tsides(self):
        pi = OutboundHardSettlement(
            target_account_id=self.test_account_id,
            internal_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            advice=True,
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.LIABILITY,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(-10),
                ),
            },
            balances,
        )

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.ASSET,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(10),
                ),
            },
            balances,
        )

    # Transfer

    def test_transfer_posting_instruction_raises_with_missing_attributes(self):
        with self.assertRaises(TypeError) as ex:
            Transfer()
        self.assertEqual(
            "Transfer.__init__() missing 4 required keyword-only arguments: 'amount', "
            "'denomination', 'debtor_target_account_id', and 'creditor_target_account_id'",
            str(ex.exception),
        )

    def test_transfer_posting_instruction_all_attributes(self):
        pi_datetime = datetime(2002, 2, 2, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        transaction_code = TransactionCode(domain="A", family="B", subfamily="C")
        pi = Transfer(
            debtor_target_account_id=self.test_account_id,
            creditor_target_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            override_all_restrictions=True,
            transaction_code=transaction_code,
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=pi_datetime,
            value_datetime=pi_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_instruction_id",
        )
        # Direct attributes
        self.assertEqual(self.test_account_id, pi.debtor_target_account_id)
        self.assertEqual("1", pi.creditor_target_account_id)
        self.assertEqual(Decimal(10), pi.amount)
        self.assertEqual("GBP", pi.denomination)
        self.assertEqual(True, pi.override_all_restrictions)
        self.assertEqual(transaction_code, pi.transaction_code)
        self.assertEqual("test", pi.instruction_details["testy"])
        # Indirect attributes
        self.assertEqual(pi_datetime, pi.value_datetime)
        self.assertEqual(pi_datetime, pi.insertion_datetime)
        self.assertEqual("instruction_id", pi.id)
        self.assertEqual("batch_id", pi.batch_id)
        self.assertEqual("CoreContracts_instruction_id", pi.unique_client_transaction_id)
        self.assertEqual("client_batch_id", pi.client_batch_id)
        # Private attributes (to be used in balances calculation)
        self.assertEqual(pi_committed_postings[0], pi._committed_postings[0])  # noqa: SLF001

    def test_transfer_posting_instruction_default_attributes_no_output_attrs(self):
        pi = Transfer(
            debtor_target_account_id=self.test_account_id,
            creditor_target_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        # Direct attributes
        self.assertEqual(self.test_account_id, pi.debtor_target_account_id)
        self.assertEqual("1", pi.creditor_target_account_id)
        self.assertEqual(Decimal(10), pi.amount)
        self.assertEqual("GBP", pi.denomination)
        self.assertEqual(False, pi.override_all_restrictions)
        self.assertIsNone(pi.transaction_code)
        self.assertEqual({}, pi.instruction_details)
        # Indirect attributes
        self.assertIsNone(pi.insertion_datetime)
        self.assertIsNone(pi.id)
        self.assertIsNone(pi.value_datetime)
        self.assertIsNone(pi.batch_id)
        self.assertIsNone(pi.unique_client_transaction_id)
        self.assertIsNone(pi.client_batch_id)
        # Private attribute used in balances calculation
        self.assertIsNone(pi._committed_postings)  # noqa: SLF001

    def test_transfer_posting_instruction_skip_type_checking(self):
        pi = Transfer(
            debtor_target_account_id=1,
            creditor_target_account_id=1,
            amount=1,
            denomination=1,
            transaction_code=1,
            instruction_details=1,
            override_all_restrictions=1,
            _from_proto=True,
        )
        # Direct attributes
        self.assertEqual(1, pi.debtor_target_account_id)
        self.assertEqual(1, pi.creditor_target_account_id)
        self.assertEqual(1, pi.amount)
        self.assertEqual(1, pi.denomination)
        self.assertEqual(1, pi.override_all_restrictions)
        self.assertEqual(1, pi.transaction_code)
        self.assertEqual(1, pi.instruction_details)

    def test_transfer_posting_instruction_raises_with_invalid_instruction_details_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            Transfer(
                debtor_target_account_id=self.test_account_id,
                creditor_target_account_id="1",
                amount=Decimal(10),
                denomination="GBP",
                override_all_restrictions=True,
                transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
                instruction_details=123,
            )

        self.assertIn(
            "'Transfer.instruction_details' expected Dict[str, str] if populated, got '123' of "
            "type int",
            str(ex.exception),
        )

    def test_transfer_posting_instruction_raises_with_invalid_transaction_code_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            Transfer(
                debtor_target_account_id=self.test_account_id,
                creditor_target_account_id="1",
                amount=Decimal(10),
                denomination="GBP",
                override_all_restrictions=True,
                transaction_code=123,
            )

        self.assertIn(
            "'Transfer.transaction_code' expected TransactionCode if populated, got '123' of type "
            "int",
            str(ex.exception),
        )

    def test_transfer_posting_instruction_balances_errors_if_own_account_id_not_provided(self):
        pi = Transfer(
            debtor_target_account_id=self.test_account_id,
            creditor_target_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )

        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "An account_id must be specified for the balances calculation.",
        ):
            pi.balances()

    def test_transfer_posting_instruction_balances_errors_if_committed_postings_not_provided(self):
        pi = Transfer(
            debtor_target_account_id=self.test_account_id,
            creditor_target_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        pi._set_output_attributes(own_account_id=self.test_account_id)  # noqa: SLF001

        with self.assertRaisesRegex(
            InvalidSmartContractError,
            "The Transfer posting instruction type does not support the balances "
            "method for the non-historical data as committed_postings are not available.",
        ):
            pi.balances()

    def test_transfer_posting_instruction_balances_for_both_tsides(self):
        pi = Transfer(
            debtor_target_account_id=self.test_account_id,
            creditor_target_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
            override_all_restrictions=True,
            transaction_code=TransactionCode(domain="A", family="B", subfamily="C"),
            instruction_details={"testy": "test"},
        )
        committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.LIABILITY,
        )

        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(-10),
                ),
            },
            balances,
        )

        pi._set_output_attributes(  # noqa: SLF001
            own_account_id=self.test_account_id,
            committed_postings=committed_postings,
            tside=Tside.ASSET,
        )
        balances = pi.balances()
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(10),
                ),
            },
            balances,
        )

    # ClientTransaction

    def test_client_transaction_transfer(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        pi = Transfer(
            debtor_target_account_id="1231234",
            creditor_target_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        self.assertEqual(trans.start_datetime, post_one_datetime)
        self.assertFalse(trans.completed())
        self.assertFalse(trans.released())
        self.assertFalse(trans.is_custom)
        self.assertEqual(trans.denomination, "GBP")
        self.assertEqual(
            {
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                ): Balance(
                    credit=Decimal(0),
                    debit=Decimal(10),
                    net=Decimal(-10),
                ),
            },
            trans.balances(),
        )
        self.assertEqual(
            ClientTransactionEffects(
                authorised=Decimal("0"),
                settled=Decimal("-10"),
                unsettled=Decimal("0"),
            ),
            trans.effects(),
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    def test_client_transaction_inbound_authorisation(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_IN,
                amount=Decimal(3),
                denomination="STONKS",
            ),
        ]
        pi = InboundAuthorisation(
            target_account_id="1231234",
            amount=Decimal(3),
            denomination="STONKS",
            client_transaction_id="out",
            internal_account_id="1",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        self.assertEqual(trans.start_datetime, post_one_datetime)
        self.assertFalse(trans.completed())
        self.assertFalse(trans.released())
        self.assertFalse(trans.is_custom)
        self.assertEqual(trans.denomination, "STONKS")
        self.assertEqual(
            {
                ("DEFAULT", "COMMERCIAL_BANK_MONEY", "STONKS", Phase.PENDING_IN): Balance(
                    credit=Decimal(3),
                    debit=Decimal(0),
                    net=Decimal(3),
                ),
            },
            trans.balances(),
        )
        self.assertEqual(
            ClientTransactionEffects(
                authorised=Decimal("3"),
                settled=Decimal("0"),
                unsettled=Decimal("3"),
            ),
            trans.effects(),
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    def test_client_transaction_outbound_authorisation(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(40),
                denomination="CAMELS",
            ),
        ]
        pi = OutboundAuthorisation(
            target_account_id="1231234",
            amount=Decimal(40),
            denomination="CAMELS",
            client_transaction_id="out",
            internal_account_id="1",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        self.assertEqual(trans.start_datetime, post_one_datetime)
        self.assertFalse(trans.completed())
        self.assertFalse(trans.released())
        self.assertFalse(trans.is_custom)
        self.assertEqual(trans.denomination, "CAMELS")
        self.assertEqual(
            {
                ("DEFAULT", "COMMERCIAL_BANK_MONEY", "CAMELS", Phase.PENDING_OUT): Balance(
                    credit=Decimal(0),
                    debit=Decimal(40),
                    net=Decimal(-40),
                ),
            },
            trans.balances(),
        )
        self.assertEqual(
            ClientTransactionEffects(
                authorised=Decimal("-40"),
                settled=Decimal("0"),
                unsettled=Decimal("-40"),
            ),
            trans.effects(),
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    def test_client_transaction_balances_raises_with_naive_datetime(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(40),
                denomination="CAMELS",
            ),
        ]
        pi = OutboundAuthorisation(
            target_account_id="1231234",
            amount=Decimal(40),
            denomination="CAMELS",
            client_transaction_id="out",
            internal_account_id="1",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        with self.assertRaises(InvalidSmartContractError) as ex:
            trans.balances(effective_datetime=datetime(2022, 1, 1))

        self.assertEqual(
            "'effective_datetime' of ClientTransaction.balances() is not timezone aware.",
            str(ex.exception),
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    def test_client_transaction_default_balance_object_before_value_datetime(self):
        before_value_datetime = datetime(2019, 12, 11, tzinfo=ZoneInfo("UTC"))
        value_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(40),
                denomination="CAMELS",
            ),
        ]
        pi = OutboundAuthorisation(
            target_account_id="1231234",
            amount=Decimal(40),
            denomination="CAMELS",
            client_transaction_id="out",
            internal_account_id="1",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=value_datetime,
            value_datetime=value_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        self.assertEqual(
            BalanceDefaultDict(),
            trans.balances(effective_datetime=before_value_datetime),
        )
        self.assertEqual(
            Balance(),
            trans.balances(effective_datetime=before_value_datetime)[
                BalanceCoordinate(
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    denomination="CAMELS",
                    phase=Phase.PENDING_OUT,
                )
            ],
        )

    def test_client_transaction_balances_raises_with_non_utc_timezone(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(40),
                denomination="CAMELS",
            ),
        ]
        pi = OutboundAuthorisation(
            target_account_id="1231234",
            amount=Decimal(40),
            denomination="CAMELS",
            client_transaction_id="out",
            internal_account_id="1",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        with self.assertRaises(InvalidSmartContractError) as ex:
            trans.balances(effective_datetime=datetime(2022, 1, 1, tzinfo=ZoneInfo("US/Pacific")))

        self.assertEqual(
            "'effective_datetime' of ClientTransaction.balances() must have timezone UTC, currently US/Pacific.",  # noqa: E501
            str(ex.exception),
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    def test_client_transaction_balances_raises_with_non_zoneinfo_timezone(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(40),
                denomination="CAMELS",
            ),
        ]
        pi = OutboundAuthorisation(
            target_account_id="1231234",
            amount=Decimal(40),
            denomination="CAMELS",
            client_transaction_id="out",
            internal_account_id="1",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        with self.assertRaises(InvalidSmartContractError) as ex:
            trans.balances(effective_datetime=datetime.fromtimestamp(1, timezone.utc))

        self.assertEqual(
            "'effective_datetime' of ClientTransaction.balances() must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(ex.exception),
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    def test_client_transaction_effects_raises_with_naive_datetime(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(40),
                denomination="CAMELS",
            ),
        ]
        pi = OutboundAuthorisation(
            target_account_id="1231234",
            amount=Decimal(40),
            denomination="CAMELS",
            client_transaction_id="out",
            internal_account_id="1",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        with self.assertRaises(InvalidSmartContractError) as ex:
            trans.effects(effective_datetime=datetime(2022, 1, 1))

        self.assertEqual(
            "'effective_datetime' of ClientTransaction.effects() is not timezone aware.",
            str(ex.exception),
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    def test_client_transaction_effects_raises_with_non_utc_timezone(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(40),
                denomination="CAMELS",
            ),
        ]
        pi = OutboundAuthorisation(
            target_account_id="1231234",
            amount=Decimal(40),
            denomination="CAMELS",
            client_transaction_id="out",
            internal_account_id="1",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        with self.assertRaises(InvalidSmartContractError) as ex:
            trans.effects(effective_datetime=datetime(2022, 1, 1, tzinfo=ZoneInfo("US/Pacific")))

        self.assertEqual(
            "'effective_datetime' of ClientTransaction.effects() must have timezone UTC, currently US/Pacific.",  # noqa: E501
            str(ex.exception),
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    def test_client_transaction_effects_default_object_before_value_datetime(self):
        before_value_datetime = datetime(2019, 12, 11, tzinfo=ZoneInfo("UTC"))
        value_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(40),
                denomination="CAMELS",
            ),
        ]
        pi = OutboundAuthorisation(
            target_account_id="1231234",
            amount=Decimal(40),
            denomination="CAMELS",
            client_transaction_id="out",
            internal_account_id="1",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=value_datetime,
            value_datetime=value_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        self.assertEqual(
            ClientTransactionEffects(),
            trans.effects(effective_datetime=before_value_datetime),
        )

    def test_client_transaction_effects_raises_with_non_zoneinfo_timezone(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(40),
                denomination="CAMELS",
            ),
        ]
        pi = OutboundAuthorisation(
            target_account_id="1231234",
            amount=Decimal(40),
            denomination="CAMELS",
            client_transaction_id="out",
            internal_account_id="1",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        with self.assertRaises(InvalidSmartContractError) as ex:
            trans.effects(effective_datetime=datetime.fromtimestamp(1, timezone.utc))

        self.assertEqual(
            "'effective_datetime' of ClientTransaction.effects() must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(ex.exception),
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    def test_client_transaction_authorisation_adjustment(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        post_two_datetime = datetime(2019, 12, 13, tzinfo=ZoneInfo("UTC"))
        pi1_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(40),
                denomination="CAMELS",
            ),
        ]
        pi1 = OutboundAuthorisation(
            target_account_id="1231234",
            amount=Decimal(40),
            denomination="CAMELS",
            client_transaction_id="out",
            internal_account_id="1",
        )
        pi1._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi1_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        pi2_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_OUT,
                amount=Decimal(7),
                denomination="CAMELS",
            ),
        ]
        pi2 = AuthorisationAdjustment(
            client_transaction_id="out", adjustment_amount=AdjustmentAmount(amount=7)
        )
        pi2._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_two_datetime,
            value_datetime=post_two_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi2_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )

        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi1, pi2],
            tside=Tside.LIABILITY,
        )
        self.assertEqual(trans.start_datetime, post_one_datetime)
        self.assertFalse(trans.completed())
        self.assertFalse(trans.released())
        self.assertFalse(trans.is_custom)
        self.assertEqual(trans.denomination, "CAMELS")
        self.assertEqual(
            {
                ("DEFAULT", "COMMERCIAL_BANK_MONEY", "CAMELS", Phase.PENDING_OUT): Balance(
                    credit=Decimal(0),
                    debit=Decimal(40),
                    net=Decimal(-40),
                ),
            },
            trans.balances(effective_datetime=post_one_datetime),
        )
        self.assertEqual(
            {
                ("DEFAULT", "COMMERCIAL_BANK_MONEY", "CAMELS", Phase.PENDING_OUT): Balance(
                    credit=Decimal(0),
                    debit=Decimal(47),
                    net=Decimal(-47),
                ),
            },
            trans.balances(effective_datetime=post_two_datetime),
        )
        self.assertEqual(
            ClientTransactionEffects(
                authorised=Decimal("-40"),
                settled=Decimal("0"),
                unsettled=Decimal("-40"),
            ),
            trans.effects(effective_datetime=post_one_datetime),
        )
        self.assertEqual(
            ClientTransactionEffects(
                authorised=Decimal("-47"),
                settled=Decimal("0"),
                unsettled=Decimal("-47"),
            ),
            trans.effects(effective_datetime=post_two_datetime),
        )
        self.assertEqual("ClientTransaction(2 posting instruction(s))", str(trans))

    def test_client_transaction_inbound_hard_settlement(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.COMMITTED,
                amount=Decimal(7),
                denomination="MONEH",
            ),
        ]
        pi = InboundHardSettlement(
            target_account_id="1231234",
            amount=Decimal(7),
            denomination="MONEH",
            internal_account_id="1",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        self.assertEqual(trans.start_datetime, post_one_datetime)
        self.assertFalse(trans.completed())
        self.assertFalse(trans.released())
        self.assertFalse(trans.is_custom)
        self.assertEqual(trans.denomination, "MONEH")
        self.assertEqual(
            {
                ("DEFAULT", "COMMERCIAL_BANK_MONEY", "MONEH", Phase.COMMITTED): Balance(
                    credit=Decimal(7),
                    debit=Decimal(0),
                    net=Decimal(7),
                ),
            },
            trans.balances(),
        )
        self.assertEqual(
            ClientTransactionEffects(
                authorised=Decimal("0"),
                settled=Decimal("7"),
                unsettled=Decimal("0"),
            ),
            trans.effects(),
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    def test_client_transaction_outbound_hard_settlement(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(666),
                denomination="APPLES",
            ),
        ]
        pi = OutboundHardSettlement(
            target_account_id="1231234",
            amount=Decimal(666),
            denomination="APPLES",
            internal_account_id="1",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        self.assertEqual(trans.start_datetime, post_one_datetime)
        self.assertFalse(trans.completed())
        self.assertFalse(trans.released())
        self.assertFalse(trans.is_custom)
        self.assertEqual(trans.denomination, "APPLES")
        self.assertEqual(
            {
                ("DEFAULT", "COMMERCIAL_BANK_MONEY", "APPLES", Phase.COMMITTED): Balance(
                    credit=Decimal(0),
                    debit=Decimal(666),
                    net=Decimal(-666),
                ),
            },
            trans.balances(),
        )
        self.assertEqual(
            ClientTransactionEffects(
                authorised=Decimal("0"),
                settled=Decimal("-666"),
                unsettled=Decimal("0"),
            ),
            trans.effects(),
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    def test_custom_instruction_client_transaction(self):
        post_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
            Posting(
                account_id="1231234",
                account_address="SOME_ADDRESS",
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
            Posting(
                account_id="1231234",
                account_address="SOME_ADDRESS",
                asset="GOLD",
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(100),
                denomination="GBP",
            ),
            Posting(
                account_id="1231234",
                account_address="SOME_ADDRESS",
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.COMMITTED,
                amount=Decimal(30),
                denomination="GBP",
            ),
        ]
        pi = CustomInstruction(postings=pi_committed_postings)
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_datetime,
            value_datetime=post_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        self.assertTrue(trans.is_custom)
        self.assertIsNone(trans.denomination)
        self.assertIsNone(trans.effects())
        self.assertEqual(trans.start_datetime, post_datetime)
        self.assertFalse(trans.completed())
        self.assertFalse(trans.released())

        self.assertEqual(
            Balance(
                credit=Decimal(0),
                debit=Decimal(10),
                net=Decimal(-10),
            ),
            trans.balances()[
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
        )
        self.assertEqual(
            Balance(
                credit=Decimal(30),
                debit=Decimal(10),
                net=Decimal(20),
            ),
            trans.balances()[
                BalanceCoordinate(
                    account_address="SOME_ADDRESS",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
        )
        self.assertEqual(
            Balance(
                credit=Decimal(0),
                debit=Decimal(100),
                net=Decimal(-100),
            ),
            trans.balances()[
                BalanceCoordinate(
                    account_address="SOME_ADDRESS",
                    asset="GOLD",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    def test_client_transaction_released(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        inbound_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_IN,
                amount=Decimal(10),
                denomination="HKK",
            ),
        ]
        post_one = InboundAuthorisation(
            amount=Decimal(10),
            target_account_id="1231234",
            denomination="HKK",
            client_transaction_id="out",
            internal_account_id="1",
        )
        post_one._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id_1",
            committed_postings=inbound_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        post_two_datetime = datetime(2020, 12, 12, tzinfo=ZoneInfo("UTC"))
        settlement_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.COMMITTED,
                amount=Decimal("0.1"),
                denomination="HKK",
            ),
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_IN,
                amount=Decimal("0.1"),
                denomination="HKK",
            ),
        ]
        post_two = Settlement(client_transaction_id="out", amount=Decimal("0.1"))
        post_two._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_two_datetime,
            value_datetime=post_two_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id_2",
            committed_postings=settlement_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
            target_account_id="1231234",
            denomination="HKK",
        )
        post_three_datetime = datetime(2021, 12, 12, tzinfo=ZoneInfo("UTC"))
        release_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_IN,
                amount=Decimal("9.9"),
                denomination="HKK",
            ),
        ]
        post_three = Release(client_transaction_id="out")
        post_three._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_three_datetime,
            value_datetime=post_three_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id_3",
            committed_postings=release_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
            target_account_id="1231234",
            denomination="HKK",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[post_one, post_two, post_three],
            tside=Tside.LIABILITY,
        )
        self.assertEqual(False, trans.completed())
        self.assertEqual(True, trans.released())
        self.assertEqual(
            False, trans.released(effective_datetime=datetime(2021, 1, 1, tzinfo=ZoneInfo("UTC")))
        )
        self.assertEqual(
            Balance(
                credit=Decimal("0.1"),
                debit=Decimal("0"),
                net=Decimal("0.1"),
            ),
            trans.balances()[
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="HKK",
                    phase=Phase.COMMITTED,
                )
            ],
        )
        self.assertEqual(
            Balance(
                credit=Decimal(10),
                debit=Decimal(10),
                net=Decimal(0),
            ),
            trans.balances()[
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="HKK",
                    phase=Phase.PENDING_IN,
                )
            ],
        )
        self.assertFalse(trans.is_custom)
        self.assertEqual(trans.denomination, "HKK")
        self.assertEqual(trans.start_datetime, post_one_datetime)
        self.assertEqual(
            ClientTransactionEffects(
                authorised=Decimal("10"),
                settled=Decimal("0.1"),
                unsettled=Decimal("0"),
            ),
            trans.effects(),
        )
        self.assertEqual("ClientTransaction(3 posting instruction(s))", str(trans))

    def test_client_transaction_completed(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        inbound_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_IN,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        post_one = InboundAuthorisation(
            amount=Decimal(10),
            target_account_id="1231234",
            denomination="GBP",
            client_transaction_id="out",
            internal_account_id="1",
        )
        post_one._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id_1",
            committed_postings=inbound_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        post_two_datetime = datetime(2020, 12, 12, tzinfo=ZoneInfo("UTC"))
        settlement_committed_postings_1 = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.COMMITTED,
                amount=Decimal("0.1"),
                denomination="GBP",
            ),
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_IN,
                amount=Decimal("0.1"),
                denomination="GBP",
            ),
        ]
        post_two = Settlement(client_transaction_id="out", amount=Decimal("0.1"))
        post_two._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_two_datetime,
            value_datetime=post_two_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id_2",
            committed_postings=settlement_committed_postings_1,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
            target_account_id="1231234",
            denomination="GBP",
        )
        post_three_datetime = datetime(2021, 12, 12, tzinfo=ZoneInfo("UTC"))
        settlement_committed_postings_2 = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.COMMITTED,
                amount=Decimal("9.9"),
                denomination="GBP",
            ),
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_IN,
                amount=Decimal("9.9"),
                denomination="GBP",
            ),
        ]
        post_three = Settlement(client_transaction_id="out", final=True)
        post_three._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_three_datetime,
            value_datetime=post_three_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id_3",
            committed_postings=settlement_committed_postings_2,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
            target_account_id="1231234",
            denomination="GBP",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[post_one, post_two, post_three],
            tside=Tside.LIABILITY,
        )
        self.assertEqual(False, trans.released())
        self.assertEqual(True, trans.completed())
        self.assertEqual(
            False, trans.completed(effective_datetime=datetime(2021, 1, 1, tzinfo=ZoneInfo("UTC")))
        )
        self.assertEqual(
            Balance(
                credit=Decimal("10"),
                debit=Decimal("0"),
                net=Decimal("10"),
            ),
            trans.balances()[
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ],
        )
        self.assertEqual(
            Balance(
                credit=Decimal(10),
                debit=Decimal(10),
                net=Decimal(0),
            ),
            trans.balances()[
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="COMMERCIAL_BANK_MONEY",
                    denomination="GBP",
                    phase=Phase.PENDING_IN,
                )
            ],
        )
        self.assertFalse(trans.is_custom)
        self.assertEqual(trans.denomination, "GBP")
        self.assertEqual(trans.start_datetime, post_one_datetime)
        self.assertEqual(
            ClientTransactionEffects(
                authorised=Decimal("10"),
                settled=Decimal("10"),
                unsettled=Decimal("0"),
            ),
            trans.effects(),
        )
        self.assertEqual("ClientTransaction(3 posting instruction(s))", str(trans))

    def test_client_transaction_invalid_committed_postings_inconsistent_ct(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        inbound_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_IN,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        post_one = InboundAuthorisation(
            amount=Decimal(10),
            target_account_id="1231234",
            denomination="GBP",
            client_transaction_id="out",
            internal_account_id="1",
        )
        post_one._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id_1",
            committed_postings=inbound_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        post_two_datetime = datetime(2020, 12, 12, tzinfo=ZoneInfo("UTC"))
        settlement_committed_postings_1 = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.COMMITTED,
                amount=Decimal("0.1"),
                denomination="GBP",
            ),
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_IN,
                amount=Decimal("0.1"),
                denomination="HKK",
            ),
        ]
        post_two = Settlement(client_transaction_id="out", amount=Decimal("0.1"))
        post_two._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_two_datetime,
            value_datetime=post_two_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id_2",
            committed_postings=settlement_committed_postings_1,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
            target_account_id="1231234",
            denomination="GBP",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[post_one, post_two],
            tside=Tside.LIABILITY,
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            trans.effects()
        self.assertEqual(
            str(ex.exception),
            "ClientTransaction only supports posting instructions with the same "
            "account_address, denomination and asset attributes.",
        )
        self.assertEqual("ClientTransaction(2 posting instruction(s))", str(trans))

    def test_client_transaction_raises_with_no_posting_instructions(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            ClientTransaction(
                client_transaction_id="out",
                account_id="1231234",
                posting_instructions=[],
            )
        self.assertEqual(
            "'ClientTransaction.posting_instructions' must be a non empty list, got []",
            str(ex.exception),
        )

    def test_client_transaction_raises_for_posting_instruction_with_no_value_datetime(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        pi = Transfer(
            debtor_target_account_id="1231234",
            creditor_target_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        # No value_datetime is set.
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            ClientTransaction(
                client_transaction_id="out",
                account_id="1231234",
                posting_instructions=[pi],
                tside=Tside.LIABILITY,
            )
        self.assertEqual(
            "'ClientTransaction.posting_instructions[0]' has its value_datetime attribute set "
            "to None. Expected value_datetime to be set.",
            str(ex.exception),
        )

    def test_client_transaction_raises_for_posting_instruction_with_no_committed_postings(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi = Transfer(
            debtor_target_account_id="1231234",
            creditor_target_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=None,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        with self.assertRaises(InvalidSmartContractError) as ex:
            ClientTransaction(
                client_transaction_id="out",
                account_id="1231234",
                posting_instructions=[pi],
                tside=Tside.LIABILITY,
            )
        self.assertEqual(
            "'ClientTransaction.posting_instructions[0]._committed_postings' "
            "must be a non empty list, got None",
            str(ex.exception),
        )

    def test_client_transaction_raises_for_posting_instruction_with_committed_postings_type(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        pi = Transfer(
            debtor_target_account_id="1231234",
            creditor_target_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=[0],
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        with self.assertRaises(StrongTypingError) as ex:
            ClientTransaction(
                client_transaction_id="out",
                account_id="1231234",
                posting_instructions=[pi],
                tside=Tside.LIABILITY,
            )
        self.assertEqual(
            "'ClientTransaction.posting_instructions[0]._committed_postings[0]' "
            "expected Posting, got '0' of type int",
            str(ex.exception),
        )

    def test_client_transaction_raises_for_settlement_attribute_final_set_to_none(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        inbound_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_IN,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        post_one = InboundAuthorisation(
            amount=Decimal(10),
            target_account_id="1231234",
            denomination="GBP",
            client_transaction_id="out",
            internal_account_id="1",
        )
        post_one._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id_1",
            committed_postings=inbound_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        post_two_datetime = datetime(2020, 12, 12, tzinfo=ZoneInfo("UTC"))
        settlement_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.COMMITTED,
                amount=Decimal("10"),
                denomination="GBP",
            ),
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.PENDING_IN,
                amount=Decimal("10"),
                denomination="GBP",
            ),
        ]
        post_two = Settlement(client_transaction_id="out", amount=Decimal("10"), final=None)
        post_two._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_two_datetime,
            value_datetime=post_two_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id_2",
            committed_postings=settlement_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
            target_account_id="1231234",
            denomination="GBP",
        )
        with self.assertRaises(InvalidPostingInstructionException) as ex:
            ClientTransaction(
                client_transaction_id="out",
                account_id="1231234",
                posting_instructions=[post_one, post_two],
                tside=Tside.LIABILITY,
            )
        self.assertEqual(
            "'ClientTransaction.posting_instructions[1]' Settlement instruction "
            "has its final attribute set to None. Expected True or False.",
            str(ex.exception),
        )

    def test_client_transaction_with_no_tside_balances(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        inbound_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_IN,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        post_one = InboundAuthorisation(
            amount=Decimal(10),
            target_account_id="1231234",
            denomination="GBP",
            client_transaction_id="out",
            internal_account_id="1",
        )
        post_one._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id_1",
            committed_postings=inbound_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[post_one],
        )
        with self.assertRaises(InvalidSmartContractError) as ex:
            trans.balances()
        self.assertEqual(
            str(ex.exception), "A tside must be specified for the balances calculation."
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    def test_client_transaction_effects_with_no_committed_postings(self):
        post_one_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))
        inbound_committed_postings = [
            Posting(
                account_id="1231234",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.PENDING_IN,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        post_one = InboundAuthorisation(
            amount=Decimal(10),
            target_account_id="1231234",
            denomination="GBP",
            client_transaction_id="out",
            internal_account_id="1",
        )
        post_one._set_output_attributes(  # noqa: SLF001
            insertion_datetime=post_one_datetime,
            value_datetime=post_one_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id_1",
            committed_postings=inbound_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        trans = ClientTransaction(
            client_transaction_id="out",
            account_id="1231234",
            posting_instructions=[post_one],
        )
        trans.posting_instructions[0]._committed_postings = None
        with self.assertRaises(InvalidSmartContractError) as ex:
            trans.effects()
        self.assertEqual(
            str(ex.exception),
            "ClientTransaction only supports posting instructions with"
            "non empty committed postings.",
        )
        self.assertEqual("ClientTransaction(1 posting instruction(s))", str(trans))

    # ClientTransactionEffects

    def test_client_transaction_effect_authorised_attribute_set(self):
        effect = ClientTransactionEffects(authorised=Decimal("40"))
        self.assertEqual(effect.authorised, Decimal("40"))
        self.assertEqual(effect.settled, Decimal("0"))
        self.assertEqual(effect.unsettled, Decimal("0"))

    def test_client_transaction_effect_settled_attribute_set(self):
        effect = ClientTransactionEffects(settled=Decimal("7"))
        self.assertEqual(effect.authorised, Decimal("0"))
        self.assertEqual(effect.settled, Decimal("7"))
        self.assertEqual(effect.unsettled, Decimal("0"))

    def test_client_transaction_effect_unsettled_attribute_set(self):
        effect = ClientTransactionEffects(unsettled=Decimal("3"))
        self.assertEqual(effect.authorised, Decimal("0"))
        self.assertEqual(effect.settled, Decimal("0"))
        self.assertEqual(effect.unsettled, Decimal("3"))

    def test_client_transaction_effect_all_attributes_set(self):
        effect = ClientTransactionEffects(
            authorised=Decimal("40"),
            settled=Decimal("7"),
            unsettled=Decimal("3"),
        )
        self.assertEqual(effect.authorised, Decimal("40"))
        self.assertEqual(effect.settled, Decimal("7"))
        self.assertEqual(effect.unsettled, Decimal("3"))

    # PostingInstructionsDirective

    def test_posting_instructions_directive(self):
        pi_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
            Posting(
                account_id="internal",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        transaction_code = TransactionCode(domain="A", family="B", subfamily="C")
        pi = CustomInstruction(
            postings=pi_postings,
            override_all_restrictions=True,
            transaction_code=transaction_code,
            instruction_details={"testy": "test"},
        )
        posting_instructions_directive = PostingInstructionsDirective(
            posting_instructions=[pi],
            client_batch_id="international-payment",
            value_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("UTC")),
        )
        self.assertEqual("international-payment", posting_instructions_directive.client_batch_id)
        self.assertEqual(
            self.test_naive_datetime.replace(tzinfo=ZoneInfo("UTC")),
            posting_instructions_directive.value_datetime,
        )
        self.assertEqual(pi, posting_instructions_directive.posting_instructions[0])
        # Both accounts postings are visible in the Postings list
        self.assertEqual(2, len(posting_instructions_directive.posting_instructions[0].postings))
        self.assertIn(
            posting_instructions_directive.posting_instructions[0].postings[0].account_id,
            [self.test_account_id, "internal"],
        )
        self.assertIn(
            posting_instructions_directive.posting_instructions[0].postings[1].account_id,
            [self.test_account_id, "internal"],
        )

        # Can get balances for in-flight CustomInstructions being directed
        self.assertEqual(
            Decimal(10),
            posting_instructions_directive.posting_instructions[0]
            .balances(account_id="internal", tside=Tside.LIABILITY)[self.balance_key_committed]
            .net,
        )
        self.assertEqual(
            Decimal(-10),
            posting_instructions_directive.posting_instructions[0]
            .balances(account_id=self.test_account_id, tside=Tside.LIABILITY)[
                self.balance_key_committed
            ]
            .net,
        )

    def test_posting_instructions_directive_value_datetime_raises_with_naive_datetime(self):
        pi_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
            Posting(
                account_id="internal",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        transaction_code = TransactionCode(domain="A", family="B", subfamily="C")
        pi = CustomInstruction(
            postings=pi_postings,
            override_all_restrictions=True,
            transaction_code=transaction_code,
            instruction_details={"testy": "test"},
        )
        with self.assertRaises(InvalidSmartContractError) as ex:
            PostingInstructionsDirective(
                posting_instructions=[pi],
                client_batch_id="international-payment",
                value_datetime=self.test_naive_datetime,
            )
        self.assertEqual(
            "'value_datetime' of PostingInstructionsDirective is not timezone aware.",
            str(ex.exception),
        )

    def test_posting_instructions_directive_value_datetime_raises_with_non_utc_timezone(self):
        pi_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
            Posting(
                account_id="internal",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        transaction_code = TransactionCode(domain="A", family="B", subfamily="C")
        pi = CustomInstruction(
            postings=pi_postings,
            override_all_restrictions=True,
            transaction_code=transaction_code,
            instruction_details={"testy": "test"},
        )
        with self.assertRaises(InvalidSmartContractError) as ex:
            PostingInstructionsDirective(
                posting_instructions=[pi],
                client_batch_id="international-payment",
                value_datetime=self.test_naive_datetime.replace(tzinfo=ZoneInfo("US/Pacific")),
            )
        self.assertEqual(
            "'value_datetime' of PostingInstructionsDirective must have timezone UTC, currently US/Pacific.",  # noqa: E501
            str(ex.exception),
        )

    def test_posting_instructions_directive_value_datetime_raises_with_non_zoneinfo_timezone(self):
        pi_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
            Posting(
                account_id="internal",
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=True,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        transaction_code = TransactionCode(domain="A", family="B", subfamily="C")
        pi = CustomInstruction(
            postings=pi_postings,
            override_all_restrictions=True,
            transaction_code=transaction_code,
            instruction_details={"testy": "test"},
        )
        with self.assertRaises(InvalidSmartContractError) as ex:
            PostingInstructionsDirective(
                posting_instructions=[pi],
                client_batch_id="international-payment",
                value_datetime=datetime.fromtimestamp(1, timezone.utc),
            )
        self.assertEqual(
            "'value_datetime' of PostingInstructionsDirective must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(ex.exception),
        )

    def test_posting_instructions_directive_defaults(self):
        pi1 = CustomInstruction(
            postings=[
                Posting(
                    account_id=self.test_account_id,
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=False,
                    phase=Phase.COMMITTED,
                    amount=Decimal(10),
                    denomination="GBP",
                ),
                Posting(
                    account_id="internal",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    credit=True,
                    phase=Phase.COMMITTED,
                    amount=Decimal(10),
                    denomination="GBP",
                ),
            ],
        )
        pi2 = CustomInstruction(
            postings=[
                Posting(
                    account_id="testty",
                    account_address="TEST",
                    asset=DEFAULT_ASSET,
                    credit=True,
                    phase=Phase.COMMITTED,
                    amount=Decimal(10),
                    denomination="GBP",
                ),
                Posting(
                    account_id="internal",
                    account_address="TEST",
                    asset=DEFAULT_ASSET,
                    credit=False,
                    phase=Phase.COMMITTED,
                    amount=Decimal(10),
                    denomination="GBP",
                ),
            ]
        )
        posting_instructions_directive = PostingInstructionsDirective(
            # Let's test this class with default values - value_datetime and client_batch_id
            # not populated!
            posting_instructions=[pi1, pi2],
        )
        self.assertIsNone(posting_instructions_directive.client_batch_id)
        self.assertIsNone(posting_instructions_directive.value_datetime)
        self.assertEqual(2, len(posting_instructions_directive.posting_instructions))
        # Both accounts postings are visible in the Postings list
        self.assertEqual(2, len(posting_instructions_directive.posting_instructions[0].postings))
        self.assertEqual(2, len(posting_instructions_directive.posting_instructions[1].postings))
        # Can get balances for in-flight CustomInstructions being directed
        self.assertEqual(
            Decimal(10),
            posting_instructions_directive.posting_instructions[0]
            .balances(account_id="internal", tside=Tside.LIABILITY)[(self.balance_key_committed)]
            .net,
        )
        self.assertEqual(
            Decimal(-10),
            posting_instructions_directive.posting_instructions[0]
            .balances(account_id=self.test_account_id, tside=Tside.LIABILITY)[
                self.balance_key_committed
            ]
            .net,
        )
        # Can get balances for in-flight CustomInstructions being directed
        self.assertEqual(
            Decimal(-10),
            posting_instructions_directive.posting_instructions[1]
            .balances(account_id="internal", tside=Tside.LIABILITY)[
                BalanceCoordinate(
                    account_address="TEST",
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ]
            .net,
        )
        self.assertEqual(
            Decimal(0),
            posting_instructions_directive.posting_instructions[1]
            .balances(account_id=self.test_account_id, tside=Tside.LIABILITY)[
                BalanceCoordinate(
                    account_address="TEST",
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ]
            .net,
        )
        self.assertEqual(
            Decimal(10),
            posting_instructions_directive.posting_instructions[1]
            .balances(account_id="testty", tside=Tside.LIABILITY)[
                BalanceCoordinate(
                    account_address="TEST",
                    asset=DEFAULT_ASSET,
                    denomination="GBP",
                    phase=Phase.COMMITTED,
                )
            ]
            .net,
        )

    def test_posting_instructions_directive_type_checking(self):
        posting_instructions_directive = PostingInstructionsDirective(
            posting_instructions=[Release(client_transaction_id="test")],
            _from_proto=True,
        )
        self.assertIsNone(posting_instructions_directive.client_batch_id)
        self.assertIsNone(posting_instructions_directive.value_datetime)
        self.assertEqual(1, len(posting_instructions_directive.posting_instructions))
        # Cannot get balances for in-flight Release
        with self.assertRaises(InvalidSmartContractError) as ex:
            posting_instructions_directive.posting_instructions[0].balances(
                account_id=self.test_account_id, tside=Tside.LIABILITY
            )
        self.assertEqual(
            "The Release posting instruction type does not support the balances method "
            "for the non-historical data as committed_postings are not available.",
            str(ex.exception),
        )

    def test_posting_instructions_directive_unsupported_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            PostingInstructionsDirective(
                posting_instructions=[Release(client_transaction_id="test")],
            )
        expected = "Expected List[CustomInstruction], got 'Release"
        self.assertIn(expected, str(ex.exception))

    def test_posting_instructions_directive_raises_no_posting_instructions(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            PostingInstructionsDirective(
                posting_instructions=[],
            )
        self.assertIn(
            "'posting_instructions' must be a non empty list, got []",
            str(ex.exception),
        )

    def test_posting_instructions_directive_skips_with_from_proto(self):
        directive = PostingInstructionsDirective(posting_instructions=[], _from_proto=True)
        self.assertEquals([], directive.posting_instructions)

    def test_posting_instructions_directive_raises_when_net_non_zero(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            PostingInstructionsDirective(
                posting_instructions=[
                    CustomInstruction(
                        postings=[
                            Posting(
                                account_address="DEFAULT",
                                account_id=self.test_account_id,
                                amount=Decimal(40),
                                denomination="GBP",
                                phase=Phase.PENDING_OUT,
                                asset=DEFAULT_ASSET,
                                credit=True,
                            ),
                            Posting(
                                account_address="DEFAULT",
                                account_id="1",
                                amount=Decimal(37),
                                denomination="GBP",
                                phase=Phase.PENDING_OUT,
                                asset=DEFAULT_ASSET,
                                credit=False,
                            ),
                        ]
                    ),
                ],
            )
        self.assertEqual(
            "Net of balance coordinate ('COMMERCIAL_BANK_MONEY', 'GBP', Phase.PENDING_OUT)"
            " in the CustomInstruction: 3, Expected: 0.",
            str(ex.exception),
        )

    def test_posting_instructions_directive_happy_path_when_net_zero(self):
        posting_instructions_directive = PostingInstructionsDirective(
            posting_instructions=[
                CustomInstruction(
                    postings=[
                        Posting(
                            account_address="DEFAULT",
                            account_id=self.test_account_id,
                            amount=Decimal(10),
                            denomination="STONKS",
                            phase=Phase.COMMITTED,
                            asset="SOMA",
                            credit=True,
                        ),
                        Posting(
                            account_address="RETIREMENT_POT",
                            account_id="1",
                            amount=Decimal(10),
                            denomination="STONKS",
                            phase=Phase.COMMITTED,
                            asset="SOMA",
                            credit=False,
                        ),
                    ]
                ),
            ],
        )

        self.assertIsNone(posting_instructions_directive.client_batch_id)
        self.assertIsNone(posting_instructions_directive.value_datetime)
        self.assertEqual(1, len(posting_instructions_directive.posting_instructions))
        self.assertEqual(2, len(posting_instructions_directive.posting_instructions[0].postings))
        self.assertEqual(
            Decimal(10),
            posting_instructions_directive.posting_instructions[0]
            .balances(account_id=self.test_account_id, tside=Tside.LIABILITY)[
                BalanceCoordinate(
                    account_address="DEFAULT",
                    asset="SOMA",
                    denomination="STONKS",
                    phase=Phase.COMMITTED,
                )
            ]
            .net,
        )
        self.assertEqual(
            Decimal(-10),
            posting_instructions_directive.posting_instructions[0]
            .balances(account_id="1", tside=Tside.LIABILITY)[
                BalanceCoordinate(
                    account_address="RETIREMENT_POT",
                    asset="SOMA",
                    denomination="STONKS",
                    phase=Phase.COMMITTED,
                )
            ]
            .net,
        )

    def test_posting_instructions_directive_raises_if_limit_of_posting_instructions_breached(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            PostingInstructionsDirective(
                posting_instructions=[
                    CustomInstruction(
                        postings=[
                            Posting(
                                amount=Decimal(1),
                                credit=True,
                                account_id="1",
                                denomination="GBP",
                                account_address=DEFAULT_ADDRESS,
                                asset=DEFAULT_ASSET,
                                phase=Phase.COMMITTED,
                            ),
                        ],
                    ),
                ]
                * 65,
            )
        self.assertIn(
            "Too many posting instructions submitted in the Posting Instructions Directive. "
            "Number submitted: 65. Limit: 64.",
            str(ex.exception),
        )

    def test_posting_instructions_directive_raises_if_limit_of_postings_in_custom_instruction_breached(  # noqa: E501
        self,
    ):
        with self.assertRaises(InvalidSmartContractError) as ex:
            PostingInstructionsDirective(
                posting_instructions=[
                    CustomInstruction(
                        postings=[
                            Posting(
                                amount=Decimal(1),
                                credit=True,
                                account_id="1",
                                denomination="GBP",
                                account_address=DEFAULT_ADDRESS,
                                asset=DEFAULT_ASSET,
                                phase=Phase.COMMITTED,
                            ),
                        ]
                        * 65,
                    ),
                ],
            )
        self.assertIn(
            "Too many postings submitted in the CustomInstruction. "
            "Number submitted: 65. Limit: 64.",
            str(ex.exception),
        )

    # Balance

    def test_balance_aggregation_add(self):
        balance_1 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_2 = Balance(credit=Decimal(10), debit=Decimal(20), net=-Decimal(10))
        aggregated_balance = balance_1 + balance_2
        self.assertEqual(30, aggregated_balance.credit)
        self.assertEqual(40, aggregated_balance.debit)
        self.assertEqual(-10, aggregated_balance.net)

    def test_balance_aggregation_iadd(self):
        aggregated_balance = Balance()
        balance_1 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_2 = Balance(credit=Decimal(10), debit=Decimal(20), net=-Decimal(10))
        aggregated_balance += balance_1
        aggregated_balance += balance_2
        self.assertEqual(30, aggregated_balance.credit)
        self.assertEqual(40, aggregated_balance.debit)
        self.assertEqual(-10, aggregated_balance.net)

    def test_balance_dict_aggregation_add(self):
        balance_1 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_2 = Balance(credit=Decimal(10), debit=Decimal(20), net=-Decimal(10))
        address = "DEFAULT"
        asset = "COMMERCIAL_BANK_MONEY"
        denomination = "GBP"
        balance_key_committed = BalanceCoordinate(
            account_address=address,
            asset=asset,
            denomination=denomination,
            phase=Phase.COMMITTED,
        )
        balance_key_out = BalanceCoordinate(
            account_address=address,
            asset=asset,
            denomination=denomination,
            phase=Phase.PENDING_OUT,
        )
        balance_key_in = BalanceCoordinate(
            account_address=address,
            asset=asset,
            denomination=denomination,
            phase=Phase.PENDING_IN,
        )

        balance_default_dict_1 = BalanceDefaultDict()
        balance_default_dict_1[balance_key_committed] = balance_1
        balance_default_dict_1[balance_key_out] = balance_1

        balance_default_dict_2 = BalanceDefaultDict()
        balance_default_dict_2[balance_key_out] = balance_2
        balance_default_dict_2[balance_key_in] = balance_2

        aggregated_balance_default_dict = balance_default_dict_1 + balance_default_dict_2

        expected_aggregated_balance_default_dict = BalanceDefaultDict()
        expected_aggregated_balance_default_dict[balance_key_committed] = balance_1
        expected_aggregated_balance_default_dict[balance_key_out] = balance_1
        expected_aggregated_balance_default_dict[balance_key_out] = balance_1 + balance_2
        expected_aggregated_balance_default_dict[balance_key_in] = balance_2

        self.assertEqual(
            expected_aggregated_balance_default_dict[balance_key_committed].net,
            aggregated_balance_default_dict[balance_key_committed].net,
        )

        self.assertEqual(
            expected_aggregated_balance_default_dict[balance_key_out].net,
            aggregated_balance_default_dict[balance_key_out].net,
        )

        self.assertEqual(
            expected_aggregated_balance_default_dict[balance_key_in].net,
            aggregated_balance_default_dict[balance_key_in].net,
        )

    def test_balance_dict_aggregation_iadd(self):
        aggregated_balance_default_dict = BalanceDefaultDict(lambda *_: Balance())
        balance_1 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_2 = Balance(credit=Decimal(10), debit=Decimal(20), net=-Decimal(10))
        address = "DEFAULT"
        asset = "COMMERCIAL_BANK_MONEY"
        denomination = "GBP"
        balance_key_committed = BalanceCoordinate(
            account_address=address, asset=asset, denomination=denomination, phase=Phase.COMMITTED
        )
        balance_key_out = BalanceCoordinate(
            account_address=address, asset=asset, denomination=denomination, phase=Phase.PENDING_OUT
        )
        balance_key_in = BalanceCoordinate(
            account_address=address, asset=asset, denomination=denomination, phase=Phase.PENDING_IN
        )

        balance_default_dict_1 = BalanceDefaultDict()
        balance_default_dict_1[balance_key_committed] = balance_1
        balance_default_dict_1[balance_key_out] = balance_1

        balance_default_dict_2 = BalanceDefaultDict()
        balance_default_dict_2[balance_key_out] = balance_2
        balance_default_dict_2[balance_key_in] = balance_2

        aggregated_balance_default_dict += balance_default_dict_1
        aggregated_balance_default_dict += balance_default_dict_2

        expected_aggregated_balance_default_dict = BalanceDefaultDict()
        expected_aggregated_balance_default_dict[balance_key_committed] = balance_1
        expected_aggregated_balance_default_dict[balance_key_out] = balance_1 + balance_2
        expected_aggregated_balance_default_dict[balance_key_in] = balance_2

        self.assertDictEqual(
            expected_aggregated_balance_default_dict, aggregated_balance_default_dict
        )

    def test_balance_aggregation_radd(self):
        balance_1 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_2 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_3 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        aggregated_balance = sum([balance_1, balance_2, balance_3], Balance())
        self.assertEqual(
            Balance(credit=Decimal(60), debit=Decimal(60), net=Decimal(0)), aggregated_balance
        )

    def test_balance_dict_aggregation_radd(self):
        balance_1 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_2 = Balance(credit=Decimal(10), debit=Decimal(20), net=-Decimal(10))
        address = "DEFAULT"
        asset = "COMMERCIAL_BANK_MONEY"
        denomination = "GBP"
        balance_key_committed = BalanceCoordinate(
            account_address=address, asset=asset, denomination=denomination, phase=Phase.COMMITTED
        )
        balance_key_out = BalanceCoordinate(
            account_address=address, asset=asset, denomination=denomination, phase=Phase.PENDING_OUT
        )
        balance_key_in = BalanceCoordinate(
            account_address=address, asset=asset, denomination=denomination, phase=Phase.PENDING_IN
        )

        balance_default_dict_1 = BalanceDefaultDict()
        balance_default_dict_1[balance_key_committed] = balance_1
        balance_default_dict_1[balance_key_out] = balance_1

        balance_default_dict_2 = BalanceDefaultDict()
        balance_default_dict_2[balance_key_out] = balance_2
        balance_default_dict_2[balance_key_in] = balance_2

        aggregated_balance_default_dict = sum(
            [balance_default_dict_1, balance_default_dict_2],
            BalanceDefaultDict(lambda *_: Balance()),
        )

        expected_aggregated_balance_default_dict = BalanceDefaultDict()
        expected_aggregated_balance_default_dict[balance_key_committed] = balance_1
        expected_aggregated_balance_default_dict[balance_key_out] = balance_1 + balance_2
        expected_aggregated_balance_default_dict[balance_key_in] = balance_2

        self.assertDictEqual(
            expected_aggregated_balance_default_dict, aggregated_balance_default_dict
        )

    def test_balance_dict_repr(self):
        balance_1 = Balance(credit=Decimal(20), debit=Decimal(20), net=Decimal(0))
        balance_2 = Balance(credit=Decimal(10), debit=Decimal(20), net=Decimal(-10))
        address = "DEFAULT"
        asset = "COMMERCIAL_BANK_MONEY"
        denomination = "GBP"
        balance_key_committed = BalanceCoordinate(
            account_address=address, asset=asset, denomination=denomination, phase=Phase.COMMITTED
        )
        balance_key_out = BalanceCoordinate(
            account_address=address, asset=asset, denomination=denomination, phase=Phase.PENDING_OUT
        )
        balance_key_in = BalanceCoordinate(
            account_address=address, asset=asset, denomination=denomination, phase=Phase.PENDING_IN
        )

        balance_dict = BalanceDefaultDict()
        balance_dict[balance_key_committed] = balance_1
        balance_dict[balance_key_out] = balance_1 + balance_2
        balance_dict[balance_key_in] = balance_2

        expected_balance_dict = (
            "{'BalanceCoordinate(account_address=DEFAULT, asset=COMMERCIAL_BANK_MONEY, "
            "denomination=GBP, phase=Phase.COMMITTED)': 'Balance(credit=20, debit=20, net=0)', "
            "'BalanceCoordinate(account_address=DEFAULT, asset=COMMERCIAL_BANK_MONEY, "
            "denomination=GBP, phase=Phase.PENDING_OUT)': 'Balance(credit=30, debit=40, net=-10)', "
            "'BalanceCoordinate(account_address=DEFAULT, asset=COMMERCIAL_BANK_MONEY, "
            "denomination=GBP, phase=Phase.PENDING_IN)': 'Balance(credit=10, debit=20, net=-10)'}"
        )
        self.assertEqual(repr(balance_dict), expected_balance_dict)

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

    def test_balances_timeseries(self):
        key_out = BalanceCoordinate(
            account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.PENDING_OUT,
        )
        key_in = BalanceCoordinate(
            account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        balances = BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase),
                (datetime(2020, 1, 15, 12, 25, 0, tzinfo=ZoneInfo("UTC")), refund),
            ]
        )
        self.assertEqual(
            balances.at(at_datetime=datetime(2020, 1, 15, 11, 20, 0, tzinfo=ZoneInfo("UTC"))),
            purchase,
        )

    def test_balances_timeseries_at_raises_with_naive_datetime(self):
        key_out = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_OUT)
        key_in = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        balances = BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase),
                (datetime(2020, 1, 15, 12, 25, 0, tzinfo=ZoneInfo("UTC")), refund),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            balances.at(at_datetime=datetime(2020, 1, 15, 11, 20, 0))
        self.assertEqual(
            "'at_datetime' of BalanceTimeseries.at() is not timezone aware.",
            str(e.exception),
        )

    def test_balances_timeseries_at_raises_with_non_utc_timezone(self):
        key_out = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_OUT)
        key_in = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        balances = BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase),
                (datetime(2020, 1, 15, 12, 25, 0, tzinfo=ZoneInfo("UTC")), refund),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            balances.at(at_datetime=datetime(2020, 1, 15, 11, 20, 0, tzinfo=ZoneInfo("US/Pacific")))
        self.assertEqual(
            "'at_datetime' of BalanceTimeseries.at() must have timezone UTC, currently US/Pacific.",  # noqa: E501
            str(e.exception),
        )

    def test_balances_timeseries_at_raises_with_non_zoneinfo_timezone(self):
        key_out = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_OUT)
        key_in = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        balances = BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase),
                (datetime(2020, 1, 15, 12, 25, 0, tzinfo=ZoneInfo("UTC")), refund),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            balances.at(at_datetime=datetime.fromtimestamp(1, timezone.utc))
        self.assertEqual(
            "'at_datetime' of BalanceTimeseries.at() must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(e.exception),
        )

    def test_balances_timeseries_before_raises_with_naive_datetime(self):
        key_out = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_OUT)
        key_in = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        balances = BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase),
                (datetime(2020, 1, 15, 12, 25, 0, tzinfo=ZoneInfo("UTC")), refund),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            balances.before(at_datetime=datetime(2020, 1, 15, 11, 20, 0))
        self.assertEqual(
            "'at_datetime' of BalanceTimeseries.before() is not timezone aware.",
            str(e.exception),
        )

    def test_balances_timeseries_before_raises_with_non_utc_timezone(self):
        key_out = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_OUT)
        key_in = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        balances = BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase),
                (datetime(2020, 1, 15, 12, 25, 0, tzinfo=ZoneInfo("UTC")), refund),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            balances.before(
                at_datetime=datetime(2020, 1, 15, 11, 20, 0, tzinfo=ZoneInfo("US/Pacific"))
            )
        self.assertEqual(
            "'at_datetime' of BalanceTimeseries.before() must have timezone UTC, currently US/Pacific.",  # noqa: E501
            str(e.exception),
        )

    def test_balances_timeseries_before_raises_with_non_zoneinfo_timezone(self):
        key_out = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_OUT)
        key_in = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        balances = BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase),
                (datetime(2020, 1, 15, 12, 25, 0, tzinfo=ZoneInfo("UTC")), refund),
            ]
        )
        with self.assertRaises(InvalidSmartContractError) as e:
            balances.before(at_datetime=datetime.fromtimestamp(1, timezone.utc))
        self.assertEqual(
            "'at_datetime' of BalanceTimeseries.before() must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(e.exception),
        )

    def test_balances_timeseries_raises_with_naive_datetime(self):
        key_out = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_OUT)
        key_in = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        with self.assertRaises(InvalidSmartContractError) as e:
            BalanceTimeseries(
                [
                    (datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase),
                    (datetime(2020, 1, 15, 12, 25, 0), refund),
                ]
            )
        self.assertEqual(str(e.exception), "'at_datetime' of TimeseriesItem is not timezone aware.")

    def test_balances_timeseries_raises_with_non_utc_datetime(self):
        key_out = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_OUT)
        key_in = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        with self.assertRaises(InvalidSmartContractError) as e:
            BalanceTimeseries(
                [
                    (datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase),
                    (datetime(2020, 1, 15, 12, 25, 0, tzinfo=ZoneInfo("US/Pacific")), refund),
                ]
            )
        self.assertEqual(
            str(e.exception),
            "'at_datetime' of TimeseriesItem must have timezone UTC, currently US/Pacific.",
        )

    def test_balances_timeseries_raises_with_non_zoneinfo_datetime(self):
        key_out = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_OUT)
        key_in = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        with self.assertRaises(InvalidSmartContractError) as e:
            BalanceTimeseries(
                [
                    (datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase),
                    (datetime.fromtimestamp(1, timezone.utc), refund),
                ]
            )
        self.assertEqual(
            str(e.exception),
            "'at_datetime' of TimeseriesItem must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
        )

    def test_balances_timeseries_return_missing_balance(self):
        balance_time = datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC"))
        purchase = (balance_time, Balance(credit=Decimal("99.99")))
        balances = BalanceTimeseries([purchase])
        self.assertEqual(balances.at(at_datetime=balance_time), purchase[1])
        self.assertEqual(
            balances.before(at_datetime=balance_time),
            Balance(credit=Decimal("0"), debit=Decimal("0"), net=Decimal("0")),
        )

    def test_balances_timeseries_return_on_empty(self):
        balances = BalanceTimeseries()
        self.assertEqual(
            balances.latest(), Balance(credit=Decimal("0"), debit=Decimal("0"), net=Decimal("0"))
        )

    def test_balance_default_dict_default_factory_happy_path(self):
        balance_default_dict = BalanceDefaultDict()
        valid_type_balance_key = BalanceCoordinate(
            account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.PENDING_OUT,
        )
        self.assertEqual(balance_default_dict[valid_type_balance_key], Balance())

    def test_balance_defaultdict_bypass_type_checking_on_init(self):
        key = BalanceCoordinate(
            account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.PENDING_OUT,
        )
        purchase = BalanceDefaultDict(mapping={key: "not_a_balance"}, _from_proto=True)
        self.assertEqual(purchase[key], "not_a_balance")

    def test_balances_timeseries_bypass_type_checking(self):
        key_out = BalanceCoordinate(
            account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.PENDING_OUT,
        )
        key_in = BalanceCoordinate(
            account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            denomination="GBP",
            phase=Phase.PENDING_IN,
        )
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        not_a_balance = "not_a_balance"
        BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase),
                (datetime(2020, 1, 15, 12, 25, 0, tzinfo=ZoneInfo("UTC")), refund),
                (datetime(2020, 1, 15, 12, 31, 0, tzinfo=ZoneInfo("UTC")), not_a_balance),
            ],
        )

    def test_balance_timeseries_all_method(self):
        key_out = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_OUT)
        key_in = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_IN)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        refund = BalanceDefaultDict(mapping={key_in: Balance(debit=Decimal(5.50))})
        balances = BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase),
                (datetime(2020, 1, 15, 12, 25, 0, tzinfo=ZoneInfo("UTC")), refund),
            ]
        )

        self.assertIsInstance(
            balances.all(),
            BalanceTimeseries,
            "BalanceTimeseries.all() must be of type BalanceTimeseries",
        )
        self.assertEqual(len(balances.all()), 2)
        self.assertEqual(
            balances.all()[0],
            TimeseriesItem((datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase)),
        )
        self.assertEqual(
            balances.all()[1],
            TimeseriesItem((datetime(2020, 1, 15, 12, 25, 0, tzinfo=ZoneInfo("UTC")), refund)),
        )

    def test_balance_timeseries_all_get_attributes(self):
        key_out = (DEFAULT_ADDRESS, DEFAULT_ASSET, "GBP", Phase.PENDING_OUT)
        purchase = BalanceDefaultDict(mapping={key_out: Balance(credit=Decimal(99.99))})
        balances = BalanceTimeseries(
            [
                (datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC")), purchase),
            ]
        )
        self.assertEqual(len(balances.all()), 1)

        timeseries_item = balances.all()[0]
        self.assertEqual(
            timeseries_item.at_datetime, datetime(2020, 1, 15, 11, 19, 0, tzinfo=ZoneInfo("UTC"))
        )
        self.assertEqual(timeseries_item.value, purchase)

    # Shift, Override, Next, Previous

    def test_shift_with_positive_values(self):
        shift = Shift(years=3, months=1, days=12, hours=4, minutes=5, seconds=6)
        self.assertEqual(3, shift.years)
        self.assertEqual(1, shift.months)
        self.assertEqual(12, shift.days)
        self.assertEqual(4, shift.hours)
        self.assertEqual(5, shift.minutes)
        self.assertEqual(6, shift.seconds)

    def test_shift_with_negative_values(self):
        shift = Shift(years=-4, months=-3, days=-2, hours=-10, minutes=-25, seconds=-45)
        self.assertEqual(-4, shift.years)
        self.assertEqual(-3, shift.months)
        self.assertEqual(-2, shift.days)
        self.assertEqual(-10, shift.hours)
        self.assertEqual(-25, shift.minutes)
        self.assertEqual(-45, shift.seconds)

    def test_shift_with_only_time_attribute_values(self):
        shift = Shift(hours=7, minutes=8, seconds=25)
        self.assertEqual(7, shift.hours)
        self.assertEqual(8, shift.minutes)
        self.assertEqual(25, shift.seconds)

    def test_shift_with_optional_values_not_provided(self):
        shift_missing_months = Shift(years=4, days=2, hours=-10, minutes=-25, seconds=-45)
        shift_missing_days = Shift(years=4, months=3, hours=-10, minutes=-25, seconds=-45)
        shift_missing_years = Shift(months=3, days=2, hours=-10, minutes=-25, seconds=-45)
        shift_missing_hours = Shift(years=4, months=3, days=2, minutes=25, seconds=45)
        shift_missing_minutes = Shift(years=2, days=2, months=3, hours=10, seconds=45)
        shift_missing_seconds = Shift(years=2, days=2, months=3, hours=10, minutes=25)

        # Confirm that values are populated with zero if left empty.
        self.assertEqual(None, shift_missing_years.years)
        self.assertEqual(None, shift_missing_months.months)
        self.assertEqual(None, shift_missing_days.days)
        self.assertEqual(None, shift_missing_hours.hours)
        self.assertEqual(None, shift_missing_minutes.minutes)
        self.assertEqual(None, shift_missing_seconds.seconds)

    def test_shift_raises_if_no_values_provided(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            Shift()

        self.assertEqual(
            str(e.exception), "Shift object needs to be populated with at least one attribute."
        )

    def test_shift_raises_if_invalid_year_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Shift(years="1")
        self.assertEqual(
            str(e.exception), "'Shift.years' expected int if populated, got '1' of type str"
        )

    def test_shift_raises_if_invalid_month_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Shift(months="1")
        self.assertEqual(
            str(e.exception), "'Shift.months' expected int if populated, got '1' of type str"
        )

    def test_shift_raises_if_invalid_day_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Shift(days="1")
        self.assertEqual(
            str(e.exception), "'Shift.days' expected int if populated, got '1' of type str"
        )

    def test_shift_raises_if_invalid_hour_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Shift(hours="1")
        self.assertEqual(
            str(e.exception), "'Shift.hours' expected int if populated, got '1' of type str"
        )

    def test_shift_raises_if_invalid_minute_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Shift(minutes="1")
        self.assertEqual(
            str(e.exception), "'Shift.minutes' expected int if populated, got '1' of type str"
        )

    def test_shift_raises_if_invalid_second_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Shift(seconds="1")
        self.assertEqual(
            str(e.exception), "'Shift.seconds' expected int if populated, got '1' of type str"
        )

    def test_defined_date_time_enum(self):
        self.assertEqual(DefinedDateTime.LIVE.value, -1)
        self.assertEqual(DefinedDateTime.INTERVAL_START.value, 2)
        self.assertEqual(DefinedDateTime.EFFECTIVE_DATETIME.value, 3)
        with self.assertRaises(AttributeError):
            DefinedDateTime.EFFECTIVE_TIME

    def test_failover_enum(self):
        self.assertEqual(ScheduleFailover.FIRST_VALID_DAY_BEFORE.value, 1)
        self.assertEqual(ScheduleFailover.FIRST_VALID_DAY_AFTER.value, 2)

    def test_override_with_valid_values(self):
        override = Override(year=2000, month=1, day=12, hour=4, minute=5, second=6)
        self.assertEqual(2000, override.year)
        self.assertEqual(1, override.month)
        self.assertEqual(12, override.day)
        self.assertEqual(4, override.hour)
        self.assertEqual(5, override.minute)
        self.assertEqual(6, override.second)

    def test_override_with_time_attributes_not_populated(self):
        override = Override(year=2000, month=1, day=12)
        self.assertEqual(2000, override.year)
        self.assertEqual(1, override.month)
        self.assertEqual(12, override.day)
        self.assertEqual(None, override.hour)
        self.assertEqual(None, override.minute)
        self.assertEqual(None, override.second)

    def test_override_with_optional_date_attribute_not_populated(self):
        override = Override(year=2000, day=12)
        self.assertEqual(2000, override.year)
        self.assertEqual(None, override.month)
        self.assertEqual(12, override.day)
        self.assertEqual(None, override.hour)
        self.assertEqual(None, override.minute)
        self.assertEqual(None, override.second)

    def test_override_raises_if_no_values_provided(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            Override()

        self.assertEqual(
            str(e.exception), "Override object needs to be populated with at least one attribute."
        )

    def test_override_raises_if_invalid_year_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Override(year="1")
        self.assertEqual(
            str(e.exception),
            "'Override.year' expected int if populated, got '1' of type str",
        )

    def test_override_raises_if_invalid_month_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Override(month="1")
        self.assertEqual(
            str(e.exception),
            "'Override.month' expected int if populated, got '1' of type str",
        )

    def test_override_raises_if_invalid_day_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Override(day="1")
        self.assertEqual(
            str(e.exception),
            "'Override.day' expected int if populated, got '1' of type str",
        )

    def test_override_raises_if_invalid_hour_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Override(hour="1")
        self.assertEqual(
            str(e.exception),
            "'Override.hour' expected int if populated, got '1' of type str",
        )

    def test_override_raises_if_invalid_minute_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Override(minute="1")
        self.assertEqual(
            str(e.exception),
            "'Override.minute' expected int if populated, got '1' of type str",
        )

    def test_override_raises_if_invalid_second_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Override(second="1")
        self.assertEqual(
            str(e.exception),
            "'Override.second' expected int if populated, got '1' of type str",
        )

    def test_override_raises_if_invalid_year_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Override(year=True)
        self.assertEqual(
            str(e.exception),
            "'Override.year' expected int if populated, got 'True' of type bool",
        )

    def test_override_raises_if_invalid_month_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Override(month=True)
        self.assertEqual(
            str(e.exception),
            "'Override.month' expected int if populated, got 'True' of type bool",
        )

    def test_override_raises_if_invalid_day_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Override(day=True)
        self.assertEqual(
            str(e.exception),
            "'Override.day' expected int if populated, got 'True' of type bool",
        )

    def test_override_raises_if_invalid_hour_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Override(hour=True)
        self.assertEqual(
            str(e.exception),
            "'Override.hour' expected int if populated, got 'True' of type bool",
        )

    def test_override_raises_if_invalid_minute_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Override(minute=True)
        self.assertEqual(
            str(e.exception),
            "'Override.minute' expected int if populated, got 'True' of type bool",
        )

    def test_override_raises_if_invalid_second_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Override(second=True)
        self.assertEqual(
            str(e.exception),
            "'Override.second' expected int if populated, got 'True' of type bool",
        )

    def test_override_raises_if_values_out_of_range(self):
        with self.assertRaises(InvalidSmartContractError) as ex1:
            Override(month=13)
        with self.assertRaises(InvalidSmartContractError) as ex2:
            Override(day=32)
        with self.assertRaises(InvalidSmartContractError) as ex3:
            Override(hour=24)
        with self.assertRaises(InvalidSmartContractError) as ex4:
            Override(minute=60)
        with self.assertRaises(InvalidSmartContractError) as ex5:
            Override(second=60)
        with self.assertRaises(InvalidSmartContractError) as ex6:
            Override(year=-1)
        with self.assertRaises(InvalidSmartContractError) as ex7:
            Override(month=0)
        with self.assertRaises(InvalidSmartContractError) as ex8:
            Override(day=0)
        with self.assertRaises(InvalidSmartContractError) as ex9:
            Override(hour=-1)
        with self.assertRaises(InvalidSmartContractError) as ex10:
            Override(minute=-1)
        with self.assertRaises(InvalidSmartContractError) as ex11:
            Override(second=-1)

        for ex in [ex1, ex2, ex3, ex4, ex5, ex6, ex7, ex8, ex9, ex10, ex11]:
            self.assertEqual(str(ex.exception), "Values of Override object are out of range.")

    def test_next_with_all_values_not_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Next()
        self.assertEqual(str(e.exception), "'Next.day' expected int, got None")

    def test_next_raises_if_invalid_month_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Next(month="1", day=1)
        self.assertEqual(
            str(e.exception), "'Next.month' expected int if populated, got '1' of type str"
        )

    def test_next_raises_if_invalid_day_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Next(day="1")
        self.assertEqual(str(e.exception), "'Next.day' expected int, got '1' of type str")

    def test_next_raises_if_invalid_hour_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Next(hour="1", day=1)
        self.assertEqual(
            str(e.exception), "'Next.hour' expected int if populated, got '1' of type str"
        )

    def test_next_raises_if_invalid_minute_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Next(minute="1", day=1)
        self.assertEqual(
            str(e.exception), "'Next.minute' expected int if populated, got '1' of type str"
        )

    def test_next_raises_if_invalid_second_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Next(second="1", day=1)
        self.assertEqual(
            str(e.exception), "'Next.second' expected int if populated, got '1' of type str"
        )

    def test_next_raises_if_invalid_month_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Next(month=True, day=1)
        self.assertEqual(
            str(e.exception), "'Next.month' expected int if populated, got 'True' of type bool"
        )

    def test_next_raises_if_invalid_day_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Next(day=True)
        self.assertEqual(str(e.exception), "'Next.day' expected int, got 'True' of type bool")

    def test_next_raises_if_invalid_hour_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Next(hour=True, day=1)
        self.assertEqual(
            str(e.exception), "'Next.hour' expected int if populated, got 'True' of type bool"
        )

    def test_next_raises_if_invalid_minute_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Next(minute=True, day=1)
        self.assertEqual(
            str(e.exception), "'Next.minute' expected int if populated, got 'True' of type bool"
        )

    def test_next_raises_if_invalid_second_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Next(second=True, day=1)
        self.assertEqual(
            str(e.exception), "'Next.second' expected int if populated, got 'True' of type bool"
        )

    def test_previous_with_all_values_not_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Previous()
        self.assertEqual(str(e.exception), "'Previous.day' expected int, got None")

    def test_previous_raises_if_invalid_month_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Previous(month="1", day=1)
        self.assertEqual(
            str(e.exception), "'Previous.month' expected int if populated, got '1' of type str"
        )

    def test_previous_raises_if_invalid_day_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Previous(day="1")
        self.assertEqual(str(e.exception), "'Previous.day' expected int, got '1' of type str")

    def test_previous_raises_if_invalid_hour_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Previous(hour="1", day=1)
        self.assertEqual(
            str(e.exception), "'Previous.hour' expected int if populated, got '1' of type str"
        )

    def test_previous_raises_if_invalid_minute_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Previous(minute="1", day=1)
        self.assertEqual(
            str(e.exception), "'Previous.minute' expected int if populated, got '1' of type str"
        )

    def test_previous_raises_if_invalid_second_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            Previous(second="1", day=1)
        self.assertEqual(
            str(e.exception), "'Previous.second' expected int if populated, got '1' of type str"
        )

    def test_previous_raises_if_invalid_month_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Previous(month=True, day=1)
        self.assertEqual(
            str(e.exception), "'Previous.month' expected int if populated, got 'True' of type bool"
        )

    def test_previous_raises_if_invalid_day_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Previous(day=True)
        self.assertEqual(str(e.exception), "'Previous.day' expected int, got 'True' of type bool")

    def test_previous_raises_if_invalid_hour_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Previous(hour=True, day=1)
        self.assertEqual(
            str(e.exception), "'Previous.hour' expected int if populated, got 'True' of type bool"
        )

    def test_previous_raises_if_invalid_minute_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Previous(minute=True, day=1)
        self.assertEqual(
            str(e.exception),
            "'Previous.minute' expected int if populated, got 'True' of type " "bool",
        )

    def test_previous_raises_if_invalid_second_types_provided_bool(self):
        with self.assertRaises(StrongTypingError) as e:
            Previous(second=True, day=1)
        self.assertEqual(
            str(e.exception),
            "'Previous.second' expected int if populated, got 'True' of type " "bool",
        )

    def test_next_with_all_values_populated(self):
        next_native_type = Next(month=1, day=12, hour=4, minute=5, second=6)
        self.assertEqual(1, next_native_type.month)
        self.assertEqual(12, next_native_type.day)
        self.assertEqual(4, next_native_type.hour)
        self.assertEqual(5, next_native_type.minute)
        self.assertEqual(6, next_native_type.second)

    def test_previous_with_all_values_populated(self):
        previous_native_type = Previous(month=5, day=17, hour=3, minute=45, second=12)
        self.assertEqual(5, previous_native_type.month)
        self.assertEqual(17, previous_native_type.day)
        self.assertEqual(3, previous_native_type.hour)
        self.assertEqual(45, previous_native_type.minute)
        self.assertEqual(12, previous_native_type.second)

    def test_next_raises_if_values_out_of_range(self):
        with self.assertRaises(InvalidSmartContractError) as ex1:
            Next(month=13, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex2:
            Next(day=32)
        with self.assertRaises(InvalidSmartContractError) as ex3:
            Next(hour=24, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex4:
            Next(minute=60, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex5:
            Next(second=60, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex6:
            Next(month=0, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex7:
            Next(day=0)

        for ex in [ex1, ex2, ex3, ex4, ex5, ex6, ex7]:
            self.assertEqual(str(ex.exception), "Values of Next object are out of range.")

    def test_previous_raises_if_values_out_of_range(self):
        with self.assertRaises(InvalidSmartContractError) as ex1:
            Previous(month=13, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex2:
            Previous(day=32)
        with self.assertRaises(InvalidSmartContractError) as ex3:
            Previous(hour=24, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex4:
            Previous(minute=60, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex5:
            Previous(second=60, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex6:
            Previous(month=0, day=2)
        with self.assertRaises(InvalidSmartContractError) as ex7:
            Previous(day=0)

        for ex in [ex1, ex2, ex3, ex4, ex5, ex6, ex7]:
            self.assertEqual(str(ex.exception), "Values of Previous object are out of range.")

    def test_relative_date_time_with_next(self):
        relative_date_time_native_object = RelativeDateTime(
            origin=DefinedDateTime.EFFECTIVE_DATETIME,
            shift=Shift(years=4, months=1, days=2, hours=-10, minutes=25, seconds=-45),
            find=Next(month=1, day=12, hour=4, minute=5, second=6),
        )

        self.assertEqual(4, relative_date_time_native_object.shift.years)
        self.assertEqual(1, relative_date_time_native_object.shift.months)
        self.assertEqual(2, relative_date_time_native_object.shift.days)
        self.assertEqual(-10, relative_date_time_native_object.shift.hours)
        self.assertEqual(25, relative_date_time_native_object.shift.minutes)
        self.assertEqual(-45, relative_date_time_native_object.shift.seconds)

        self.assertEqual(1, relative_date_time_native_object.find.month)
        self.assertEqual(12, relative_date_time_native_object.find.day)
        self.assertEqual(4, relative_date_time_native_object.find.hour)
        self.assertEqual(5, relative_date_time_native_object.find.minute)
        self.assertEqual(6, relative_date_time_native_object.find.second)

        self.assertEqual(
            DefinedDateTime.EFFECTIVE_DATETIME, relative_date_time_native_object.origin
        )

    def test_relative_date_time_with_previous(self):
        relative_date_time_native_object = RelativeDateTime(
            origin=DefinedDateTime.EFFECTIVE_DATETIME,
            shift=Shift(years=4, months=1, days=2, hours=-10, minutes=25, seconds=-45),
            find=Previous(month=1, day=12, hour=6, minute=7, second=25),
        )

        self.assertEqual(4, relative_date_time_native_object.shift.years)
        self.assertEqual(1, relative_date_time_native_object.shift.months)
        self.assertEqual(2, relative_date_time_native_object.shift.days)
        self.assertEqual(-10, relative_date_time_native_object.shift.hours)
        self.assertEqual(25, relative_date_time_native_object.shift.minutes)
        self.assertEqual(-45, relative_date_time_native_object.shift.seconds)

        self.assertEqual(1, relative_date_time_native_object.find.month)
        self.assertEqual(12, relative_date_time_native_object.find.day)
        self.assertEqual(6, relative_date_time_native_object.find.hour)
        self.assertEqual(7, relative_date_time_native_object.find.minute)
        self.assertEqual(25, relative_date_time_native_object.find.second)

        self.assertEqual(
            DefinedDateTime.EFFECTIVE_DATETIME, relative_date_time_native_object.origin
        )

    def test_relative_date_time_raises_if_invalid_shift_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            RelativeDateTime(shift="1", origin=DefinedDateTime.EFFECTIVE_DATETIME)
        self.assertEqual(
            str(e.exception),
            "'RelativeDateTime.shift' expected Shift if populated, got '1' of type str",
        )

    def test_relative_date_time_raises_if_invalid_find_types_provided(self):
        with self.assertRaises(StrongTypingError) as e:
            RelativeDateTime(find="1", origin=DefinedDateTime.EFFECTIVE_DATETIME)
        self.assertEqual(
            str(e.exception),
            "'RelativeDateTime.find' expected Union[Next, Previous, Override] if populated, got "
            "'1' of type str",
        )

    def test_relative_date_time_with_shift_and_find_not_populated(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            RelativeDateTime(origin=DefinedDateTime.EFFECTIVE_DATETIME)

        self.assertEqual(
            str(ex.exception),
            "RelativeDateTime Object requires either shift or find attributes to be populated",
        )

    def test_relative_date_time_with_override(self):
        relative_date_time_native_object = RelativeDateTime(
            origin=DefinedDateTime.EFFECTIVE_DATETIME,
            shift=Shift(years=4, months=1, days=2, hours=-10, minutes=25, seconds=-45),
            find=Override(year=2, month=1, day=12, hour=2, minute=9, second=53),
        )

        self.assertEqual(4, relative_date_time_native_object.shift.years)
        self.assertEqual(1, relative_date_time_native_object.shift.months)
        self.assertEqual(2, relative_date_time_native_object.shift.days)
        self.assertEqual(-10, relative_date_time_native_object.shift.hours)
        self.assertEqual(25, relative_date_time_native_object.shift.minutes)
        self.assertEqual(-45, relative_date_time_native_object.shift.seconds)

        self.assertEqual(2, relative_date_time_native_object.find.year)
        self.assertEqual(1, relative_date_time_native_object.find.month)
        self.assertEqual(12, relative_date_time_native_object.find.day)
        self.assertEqual(2, relative_date_time_native_object.find.hour)
        self.assertEqual(9, relative_date_time_native_object.find.minute)
        self.assertEqual(53, relative_date_time_native_object.find.second)

        self.assertEqual(
            DefinedDateTime.EFFECTIVE_DATETIME, relative_date_time_native_object.origin
        )

    def test_relative_date_time_with_origin_interval_start(self):
        relative_date_time_native_object = RelativeDateTime(
            shift=Shift(years=4, months=1, days=2, hours=-10, minutes=25, seconds=-45),
            find=Override(year=2, month=1, day=12, hour=2, minute=9, second=53),
            origin=DefinedDateTime.INTERVAL_START,
        )

        self.assertEqual(4, relative_date_time_native_object.shift.years)
        self.assertEqual(1, relative_date_time_native_object.shift.months)
        self.assertEqual(2, relative_date_time_native_object.shift.days)
        self.assertEqual(-10, relative_date_time_native_object.shift.hours)
        self.assertEqual(25, relative_date_time_native_object.shift.minutes)
        self.assertEqual(-45, relative_date_time_native_object.shift.seconds)

        self.assertEqual(2, relative_date_time_native_object.find.year)
        self.assertEqual(1, relative_date_time_native_object.find.month)
        self.assertEqual(12, relative_date_time_native_object.find.day)
        self.assertEqual(2, relative_date_time_native_object.find.hour)
        self.assertEqual(9, relative_date_time_native_object.find.minute)
        self.assertEqual(53, relative_date_time_native_object.find.second)

        self.assertEqual(DefinedDateTime.INTERVAL_START, relative_date_time_native_object.origin)

    def test_relative_date_time_with_origin_using_illegal_live_value(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            RelativeDateTime(
                shift=Shift(years=4, months=1, days=2, hours=-10, minutes=25, seconds=-45),
                find=Override(year=2, month=1, day=12, hour=2, minute=9, second=53),
                origin=DefinedDateTime.LIVE,
            )
        self.assertEqual(
            str(ex.exception),
            'RelativeDateTime origin attribute does not support "DefinedDateTime.LIVE"',
        )

    # PostingsIntervalFetcher

    def test_postings_interval_fetcher_with_relative_datetime_start(self):
        postings_interval_fetcher = PostingsIntervalFetcher(
            fetcher_id="fetcher_id",
            start=RelativeDateTime(
                origin=DefinedDateTime.EFFECTIVE_DATETIME, shift=Shift(years=-1, months=2)
            ),
            end=DefinedDateTime.EFFECTIVE_DATETIME,
        )

        self.assertEqual("fetcher_id", postings_interval_fetcher.fetcher_id)

        self.assertEqual(-1, postings_interval_fetcher.start.shift.years)
        self.assertEqual(2, postings_interval_fetcher.start.shift.months)
        self.assertEqual(DefinedDateTime.EFFECTIVE_DATETIME, postings_interval_fetcher.end)

    def test_postings_interval_fetcher_errors_without_start(self):
        with self.assertRaises(StrongTypingError) as e:
            PostingsIntervalFetcher(fetcher_id="fetcher_id", end=DefinedDateTime.EFFECTIVE_DATETIME)
        self.assertEqual(
            str(e.exception),
            "'PostingsIntervalFetcher.start' expected Union[RelativeDateTime, DefinedDateTime], "
            "got None",
        )

    def test_postings_interval_fetcher_errors_without_id(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            PostingsIntervalFetcher(
                start=RelativeDateTime(
                    origin=DefinedDateTime.EFFECTIVE_DATETIME, shift=Shift(years=-1, months=2)
                ),
                end=DefinedDateTime.EFFECTIVE_DATETIME,
            )
        self.assertEqual(
            str(e.exception),
            "PostingsIntervalFetcher 'fetcher_id' must be populated",
        )

    def test_postings_interval_fetcher_errors_with_empty_id(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            PostingsIntervalFetcher(
                fetcher_id="",
                start=RelativeDateTime(
                    origin=DefinedDateTime.EFFECTIVE_DATETIME, shift=Shift(years=-1, months=2)
                ),
                end=DefinedDateTime.EFFECTIVE_DATETIME,
            )
        self.assertEqual(
            str(e.exception),
            "PostingsIntervalFetcher 'fetcher_id' must be populated",
        )

    def test_postings_interval_fetcher_succeeds_without_end(self):
        postings_interval_fetcher = PostingsIntervalFetcher(
            fetcher_id="fetcher_id",
            start=RelativeDateTime(
                origin=DefinedDateTime.EFFECTIVE_DATETIME, shift=Shift(years=-1, months=2)
            ),
        )
        self.assertEqual("fetcher_id", postings_interval_fetcher.fetcher_id)

        self.assertEqual(-1, postings_interval_fetcher.start.shift.years)
        self.assertEqual(2, postings_interval_fetcher.start.shift.months)
        self.assertEqual(DefinedDateTime.LIVE, postings_interval_fetcher.end)

    def test_postings_interval_fetcher_with_defined_datetime_start(self):
        postings_interval_fetcher = PostingsIntervalFetcher(
            fetcher_id="fetcher_id", start=DefinedDateTime.EFFECTIVE_DATETIME
        )
        self.assertEqual("fetcher_id", postings_interval_fetcher.fetcher_id)
        self.assertEqual(DefinedDateTime.EFFECTIVE_DATETIME, postings_interval_fetcher.start)
        self.assertEqual(DefinedDateTime.LIVE, postings_interval_fetcher.end)

    def test_postings_interval_fetcher_errors_with_live_start(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            PostingsIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.LIVE,
            )
        self.assertEqual(
            str(e.exception),
            "PostingsIntervalFetcher 'start' cannot be set to 'DefinedDateTime.LIVE'",
        )

    def test_postings_interval_fetcher_between_effective_and_live(self):
        postings_interval_fetcher = PostingsIntervalFetcher(
            fetcher_id="fetcher_id",
            start=DefinedDateTime.EFFECTIVE_DATETIME,
            end=DefinedDateTime.LIVE,
        )
        self.assertEqual(DefinedDateTime.EFFECTIVE_DATETIME, postings_interval_fetcher.start)
        self.assertEqual(DefinedDateTime.LIVE, postings_interval_fetcher.end)

    def test_postings_interval_fetcher_errors_with_invalid_start(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            PostingsIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.INTERVAL_START,
            )
        self.assertEqual(
            str(e.exception),
            "PostingsIntervalFetcher 'start' cannot be set to 'DefinedDateTime.INTERVAL_START'",
        )

    def test_postings_interval_fetcher_errors_with_invalid_end(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            PostingsIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.EFFECTIVE_DATETIME,
                end=DefinedDateTime.INTERVAL_START,
            )
        self.assertEqual(
            str(e.exception),
            "PostingsIntervalFetcher 'end' cannot be set to 'DefinedDateTime.INTERVAL_START'",
        )

    def test_postings_interval_fetcher_errors_with_invalid_start_origin(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            PostingsIntervalFetcher(
                fetcher_id="fetcher_id",
                start=RelativeDateTime(
                    origin=DefinedDateTime.INTERVAL_START, shift=Shift(years=-1)
                ),
            )
        self.assertEqual(
            str(e.exception),
            "PostingsIntervalFetcher 'start' origin value must be set to "
            "'DefinedDateTime.EFFECTIVE_DATETIME'",
        )

    def test_postings_interval_fetcher_raises_with_invalid_start_type(self):
        with self.assertRaises(StrongTypingError) as e:
            PostingsIntervalFetcher(
                fetcher_id="fetcher_id",
                start="foo",
            )

        self.assertEqual(
            str(e.exception),
            "'PostingsIntervalFetcher.start' expected Union[RelativeDateTime, DefinedDateTime], "
            "got 'foo' of type str",
        )

    def test_postings_interval_fetcher_raises_with_invalid_end_type(self):
        with self.assertRaises(StrongTypingError) as e:
            PostingsIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.EFFECTIVE_DATETIME,
                end="foo",
            )

        self.assertEqual(
            str(e.exception),
            "'PostingsIntervalFetcher.end' expected Union[RelativeDateTime, DefinedDateTime] if "
            "populated, got 'foo' of type str",
        )

    # BalancesIntervalFetcher

    def test_balances_interval_fetcher_with_relative_datetime_start(self):
        balances_interval_fetcher = BalancesIntervalFetcher(
            fetcher_id="fetcher_id",
            start=RelativeDateTime(
                origin=DefinedDateTime.EFFECTIVE_DATETIME, shift=Shift(years=-1, months=2)
            ),
            end=DefinedDateTime.EFFECTIVE_DATETIME,
        )

        self.assertEqual("fetcher_id", balances_interval_fetcher.fetcher_id)

        self.assertEqual(-1, balances_interval_fetcher.start.shift.years)
        self.assertEqual(2, balances_interval_fetcher.start.shift.months)
        self.assertEqual(DefinedDateTime.EFFECTIVE_DATETIME, balances_interval_fetcher.end)

    def test_balances_interval_fetcher_errors_without_start(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesIntervalFetcher(fetcher_id="fetcher_id", end=DefinedDateTime.EFFECTIVE_DATETIME)
        self.assertEqual(
            str(e.exception),
            "'BalancesIntervalFetcher.start' expected Union[RelativeDateTime, DefinedDateTime], "
            "got None",
        )

    def test_balances_interval_fetcher_errors_without_id(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesIntervalFetcher(
                start=RelativeDateTime(
                    origin=DefinedDateTime.EFFECTIVE_DATETIME, shift=Shift(years=-1, months=2)
                ),
                end=DefinedDateTime.EFFECTIVE_DATETIME,
            )
        self.assertEqual(
            str(e.exception),
            "BalancesIntervalFetcher 'fetcher_id' must be populated",
        )

    def test_balances_interval_fetcher_errors_with_empty_id(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesIntervalFetcher(
                fetcher_id="",
                start=RelativeDateTime(
                    origin=DefinedDateTime.EFFECTIVE_DATETIME, shift=Shift(years=-1, months=2)
                ),
                end=DefinedDateTime.EFFECTIVE_DATETIME,
            )
        self.assertEqual(
            str(e.exception),
            "BalancesIntervalFetcher 'fetcher_id' must be populated",
        )

    def test_balances_interval_fetcher_succeeds_without_end(self):
        balances_interval_fetcher = BalancesIntervalFetcher(
            fetcher_id="fetcher_id",
            start=RelativeDateTime(
                origin=DefinedDateTime.EFFECTIVE_DATETIME, shift=Shift(years=-1, months=2)
            ),
        )
        self.assertEqual("fetcher_id", balances_interval_fetcher.fetcher_id)

        self.assertEqual(-1, balances_interval_fetcher.start.shift.years)
        self.assertEqual(2, balances_interval_fetcher.start.shift.months)
        self.assertEqual(DefinedDateTime.LIVE, balances_interval_fetcher.end)

    def test_balances_interval_fetcher_with_defined_datetime_start(self):
        balances_interval_fetcher = BalancesIntervalFetcher(
            fetcher_id="fetcher_id", start=DefinedDateTime.EFFECTIVE_DATETIME
        )
        self.assertEqual("fetcher_id", balances_interval_fetcher.fetcher_id)
        self.assertEqual(DefinedDateTime.EFFECTIVE_DATETIME, balances_interval_fetcher.start)
        self.assertEqual(DefinedDateTime.LIVE, balances_interval_fetcher.end)

    def test_balances_interval_fetcher_errors_with_live_start(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.LIVE,
            )
        self.assertEqual(
            str(e.exception),
            "BalancesIntervalFetcher 'start' cannot be set to 'DefinedDateTime.LIVE'",
        )

    def test_balances_interval_fetcher_between_effective_and_live(self):
        balances_interval_fetcher = BalancesIntervalFetcher(
            fetcher_id="fetcher_id",
            start=DefinedDateTime.EFFECTIVE_DATETIME,
            end=DefinedDateTime.LIVE,
        )
        self.assertEqual(DefinedDateTime.EFFECTIVE_DATETIME, balances_interval_fetcher.start)
        self.assertEqual(DefinedDateTime.LIVE, balances_interval_fetcher.end)

    def test_balances_interval_fetcher_errors_with_invalid_start(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.INTERVAL_START,
            )
        self.assertEqual(
            str(e.exception),
            "BalancesIntervalFetcher 'start' cannot be set to 'DefinedDateTime.INTERVAL_START'",
        )

    def test_balances_interval_fetcher_errors_with_invalid_end(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.EFFECTIVE_DATETIME,
                end=DefinedDateTime.INTERVAL_START,
            )
        self.assertEqual(
            str(e.exception),
            "BalancesIntervalFetcher 'end' cannot be set to 'DefinedDateTime.INTERVAL_START'",
        )

    def test_balances_interval_fetcher_errors_with_invalid_start_origin(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesIntervalFetcher(
                fetcher_id="fetcher_id",
                start=RelativeDateTime(
                    origin=DefinedDateTime.INTERVAL_START, shift=Shift(years=-1)
                ),
            )
        self.assertEqual(
            str(e.exception),
            "BalancesIntervalFetcher 'start' origin value must be set to "
            "'DefinedDateTime.EFFECTIVE_DATETIME'",
        )

    def test_balances_interval_fetcher_with_filter(self):
        filter = BalancesFilter(addresses=["CUSTOM_ADDRESS", "DEFAULT_ADDRESS"])
        balances_interval_fetcher = BalancesIntervalFetcher(
            fetcher_id="fetcher_id",
            start=DefinedDateTime.EFFECTIVE_DATETIME,
            end=DefinedDateTime.LIVE,
            filter=filter,
        )
        self.assertEqual(DefinedDateTime.EFFECTIVE_DATETIME, balances_interval_fetcher.start)
        self.assertEqual(DefinedDateTime.LIVE, balances_interval_fetcher.end)
        self.assertEqual(filter, balances_interval_fetcher.filter)

    def test_balances_interval_fetcher_raises_with_invalid_filter_type(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.EFFECTIVE_DATETIME,
                end=DefinedDateTime.LIVE,
                filter=123,
            )

        self.assertEqual(
            str(e.exception),
            "'BalancesIntervalFetcher.filter' expected BalancesFilter if populated, got '123' of "
            "type int",
        )

    def test_balances_interval_fetcher_raises_with_invalid_start_type(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesIntervalFetcher(
                fetcher_id="fetcher_id",
                start="foo",
            )

        self.assertEqual(
            str(e.exception),
            "'BalancesIntervalFetcher.start' expected Union[RelativeDateTime, DefinedDateTime], "
            "got 'foo' of type str",
        )

    def test_balances_interval_fetcher_raises_with_invalid_end_type(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesIntervalFetcher(
                fetcher_id="fetcher_id",
                start=DefinedDateTime.EFFECTIVE_DATETIME,
                end="foo",
            )

        self.assertEqual(
            str(e.exception),
            "'BalancesIntervalFetcher.end' expected Union[RelativeDateTime, DefinedDateTime] if "
            "populated, got 'foo' of type str",
        )

    # BalancesObservationFetcher

    def test_balances_observation_fetcher_with_defined_datetime(self):
        filter = BalancesFilter(addresses=["CUSTOM_ADDRESS", "DEFAULT_ADDRESS"])
        balances_observation_fetcher = BalancesObservationFetcher(
            fetcher_id="fetcher_id", at=DefinedDateTime.EFFECTIVE_DATETIME, filter=filter
        )
        self.assertEqual("fetcher_id", balances_observation_fetcher.fetcher_id)
        self.assertEqual(DefinedDateTime.EFFECTIVE_DATETIME, balances_observation_fetcher.at)
        self.assertEqual(filter, balances_observation_fetcher.filter)

    def test_balances_observation_fetcher_with_relative_datetime(self):
        filter = BalancesFilter(addresses=["CUSTOM_ADDRESS", "DEFAULT_ADDRESS"])
        relative_date_time = RelativeDateTime(
            shift=Shift(months=-1), origin=DefinedDateTime.EFFECTIVE_DATETIME
        )
        balances_observation_fetcher = BalancesObservationFetcher(
            fetcher_id="fetcher_id", at=relative_date_time, filter=filter
        )
        self.assertEqual("fetcher_id", balances_observation_fetcher.fetcher_id)
        self.assertEqual(relative_date_time, balances_observation_fetcher.at)
        self.assertEqual(filter, balances_observation_fetcher.filter)

    def test_balances_observation_fetcher_with_no_filter(self):
        relative_date_time = RelativeDateTime(
            shift=Shift(months=-1), origin=DefinedDateTime.EFFECTIVE_DATETIME
        )
        balances_observation_fetcher = BalancesObservationFetcher(
            fetcher_id="fetcher_id",
            at=relative_date_time,
        )
        self.assertEqual("fetcher_id", balances_observation_fetcher.fetcher_id)
        self.assertEqual(relative_date_time, balances_observation_fetcher.at)

    def test_balances_observation_fetcher_raises_with_empty_fetcher_id(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesObservationFetcher(
                fetcher_id="",
                at=RelativeDateTime(
                    shift=Shift(months=-1), origin=DefinedDateTime.EFFECTIVE_DATETIME
                ),
            )

        self.assertEqual(
            str(e.exception), "'BalancesObservationFetcher.fetcher_id' must be a non-empty string"
        )

    def test_balances_observation_fetcher_raises_with_fetcher_id_not_populated(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesObservationFetcher(
                at=RelativeDateTime(
                    shift=Shift(months=-1), origin=DefinedDateTime.EFFECTIVE_DATETIME
                )
            )

        self.assertEqual(
            str(e.exception),
            "'BalancesObservationFetcher.fetcher_id' expected str, got None",
        )

    def test_balances_observation_fetcher_raises_with_fetcher_id_invalid_type(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesObservationFetcher(
                fetcher_id=42,
                at=RelativeDateTime(
                    shift=Shift(months=-1), origin=DefinedDateTime.EFFECTIVE_DATETIME
                ),
            )

        self.assertEqual(
            str(e.exception),
            "'BalancesObservationFetcher.fetcher_id' expected str, got '42' of type int",
        )

    def test_balances_observation_fetcher_raises_if_at_attribute_not_populated(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesObservationFetcher(
                fetcher_id="fetcher_id",
            )

        self.assertEqual(
            str(e.exception),
            "BalancesObservationFetcher 'at' must be populated",
        )

    def test_balances_observation_fetcher_raises_if_at_populated_with_interval_start(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesObservationFetcher(
                fetcher_id="fetcher_id",
                at=DefinedDateTime.INTERVAL_START,
            )

        self.assertEqual(
            str(e.exception),
            "BalancesObservationFetcher 'at' cannot be set to 'DefinedDateTime.INTERVAL_START'",
        )

    def test_balances_observation_fetcher_raises_with_invalid_filter_type(self):
        relative_date_time = RelativeDateTime(
            shift=Shift(months=-1), origin=DefinedDateTime.EFFECTIVE_DATETIME
        )
        with self.assertRaises(StrongTypingError) as e:
            BalancesObservationFetcher(fetcher_id="fetcher_id", at=relative_date_time, filter=123)
        self.assertEqual(
            str(e.exception),
            "'BalancesObservationFetcher.filter' expected BalancesFilter if populated, got '123' "
            "of type int",
        )

    def test_balances_observation_fetcher_raises_with_invalid_at_type(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesObservationFetcher(fetcher_id="fetcher_id", at="foo")
        self.assertEqual(
            str(e.exception),
            "'BalancesObservationFetcher.at' expected Union[DefinedDateTime, RelativeDateTime], "
            "got 'foo' of type str",
        )

    # BalancesObservation

    def test_balances_observation(self):
        value_datetime = datetime(year=2020, month=2, day=20, tzinfo=ZoneInfo("UTC"))
        balance_key_1 = BalanceCoordinate(
            account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            denomination="USD",
            phase=Phase.COMMITTED,
        )
        balance_dict = BalanceDefaultDict()
        balance_dict[balance_key_1] = Balance(net=Decimal("20"), credit=Decimal("20"))
        balances_observation = BalancesObservation(
            value_datetime=value_datetime, balances=balance_dict
        )
        self.assertEqual(balance_dict, balances_observation.balances)
        self.assertEqual(value_datetime, balances_observation.value_datetime)

    def test_balances_observation_raises_with_wrong_balances_type(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesObservation(balances=None)
        self.assertEqual(
            str(e.exception),
            "'BalancesObservation.balances' expected BalanceDefaultDict, got None",
        )

    def test_balances_observation_raises_with_naive_datetime(self):
        value_datetime = datetime(year=2020, month=2, day=20)
        balance_dict = BalanceDefaultDict()
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesObservation(value_datetime=value_datetime, balances=balance_dict)
        self.assertEqual(
            str(e.exception),
            "'value_datetime' of BalancesObservation is not timezone aware.",
        )

    def test_balances_observation_raises_with_non_utc_timezone(self):
        value_datetime = datetime(year=2020, month=2, day=20, tzinfo=ZoneInfo("US/Pacific"))
        balance_dict = BalanceDefaultDict()
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesObservation(value_datetime=value_datetime, balances=balance_dict)
        self.assertEqual(
            str(e.exception),
            "'value_datetime' of BalancesObservation must have timezone UTC, currently "
            "US/Pacific.",
        )

    def test_balances_observation_raises_with_non_zoneinfo_timezone(self):
        value_datetime = datetime.fromtimestamp(1, timezone.utc)
        balance_dict = BalanceDefaultDict()
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesObservation(value_datetime=value_datetime, balances=balance_dict)
        self.assertEqual(
            "'value_datetime' of BalancesObservation must have timezone of type ZoneInfo, currently <class 'datetime.timezone'>.",  # noqa: E501
            str(e.exception),
        )

    def test_balances_observation_no_value_datetime_and_empty_balances(self):
        balance_dict = BalanceDefaultDict()
        balances_observation = BalancesObservation(value_datetime=None, balances=balance_dict)
        self.assertEqual(None, balances_observation.value_datetime)
        self.assertEqual(balance_dict, balances_observation.balances)

    

    # ScheduledEvent

    def test_scheduled_event(self):
        start_datetime = datetime(year=2000, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end_datetime = datetime(year=2000, month=2, day=1, tzinfo=ZoneInfo("UTC"))
        schedule_expression = ScheduleExpression(day="5")
        skip = ScheduleSkip(
            end=datetime(year=2000, month=1, day=20, tzinfo=ZoneInfo("UTC")),
        )

        scheduled_event = ScheduledEvent(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            expression=schedule_expression,
            skip=skip,
        )
        self.assertEqual(start_datetime, scheduled_event.start_datetime)
        self.assertEqual(end_datetime, scheduled_event.end_datetime)
        self.assertEqual(schedule_expression, scheduled_event.expression)
        self.assertEqual(skip, scheduled_event.skip)

    def test_scheduled_event_raises_with_naive_start_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            ScheduledEvent(
                start_datetime=datetime(2022, 1, 1),
            )
        self.assertIn(
            "'start_datetime' of ScheduledEvent is not timezone aware.",
            str(ex.exception),
        )

    def test_scheduled_event_raises_with_naive_end_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(2022, 1, 1),
            )
        self.assertEqual(
            "'end_datetime' of ScheduledEvent is not timezone aware.",
            str(ex.exception),
        )

    def test_scheduled_event_raises_with_naive_skip_end_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                skip=ScheduleSkip(
                    end=datetime(year=2000, month=1, day=20),
                ),
            )
        self.assertEqual(
            "'end' of ScheduleSkip is not timezone aware.",
            str(ex.exception),
        )

    def test_scheduled_event_schedule_method(self):
        start_datetime = datetime(year=2000, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end_datetime = datetime(year=2000, month=2, day=1, tzinfo=ZoneInfo("UTC"))
        schedule_method = EndOfMonthSchedule(day=5)

        scheduled_event = ScheduledEvent(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            schedule_method=schedule_method,
        )
        self.assertEqual(start_datetime, scheduled_event.start_datetime)
        self.assertEqual(end_datetime, scheduled_event.end_datetime)
        self.assertEqual(schedule_method, scheduled_event.schedule_method)

    def test_scheduled_event_with_no_start_end_datetimes(self):
        schedule_expression = ScheduleExpression(day="5")
        scheduled_event = ScheduledEvent(expression=schedule_expression)
        self.assertEqual(None, scheduled_event.start_datetime)
        self.assertEqual(None, scheduled_event.end_datetime)
        self.assertEqual(schedule_expression, scheduled_event.expression)

    def test_scheduled_event_invalid_start_datetime_raises(self):
        with self.assertRaises(StrongTypingError) as e:
            ScheduledEvent(
                start_datetime=True,
                end_datetime=datetime(year=2000, month=2, day=1),
                expression=ScheduleExpression(day="5"),
            )
        self.assertEqual(
            "'ScheduledEvent.start_datetime' expected datetime if populated, "
            "got 'True' of type bool",
            str(e.exception),
        )

    def test_scheduled_event_no_end_datetime(self):
        start_datetime = datetime(year=2000, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        schedule_expression = ScheduleExpression(day="5")

        scheduled_event = ScheduledEvent(
            start_datetime=start_datetime,
            expression=schedule_expression,
        )
        self.assertEqual(start_datetime, scheduled_event.start_datetime)
        self.assertEqual(None, scheduled_event.end_datetime)
        self.assertEqual(schedule_expression, scheduled_event.expression)

    def test_scheduled_event_invalid_end_datetime_raises(self):
        with self.assertRaises(StrongTypingError) as e:
            ScheduledEvent(
                start_datetime=datetime(year=2000, month=1, day=1, tzinfo=ZoneInfo("UTC")),
                end_datetime=True,
                expression=ScheduleExpression(day="5"),
            )
        self.assertEqual(
            "'ScheduledEvent.end_datetime' expected datetime if populated, got 'True' of type "
            "bool",
            str(e.exception),
        )

    def test_scheduled_event_no_end_datetime_expression_schedule_method_or_skip_raises(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            ScheduledEvent(
                start_datetime=datetime(year=2000, month=1, day=1, tzinfo=ZoneInfo("UTC")),
            )
        self.assertEqual(
            "ScheduledEvent must have an end_datetime, expression, schedule_method or skip set",
            str(e.exception),
        )

    def test_scheduled_event_expression_and_schedule_method_raises(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            ScheduledEvent(
                start_datetime=datetime(year=2000, month=1, day=1, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(year=2000, month=2, day=1, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(day="5"),
                schedule_method=EndOfMonthSchedule(day=5),
            )
        self.assertEqual(
            "ScheduledEvent must not have both expression and schedule_method set",
            str(e.exception),
        )

    def test_scheduled_event_invalid_expression_raises(self):
        with self.assertRaises(StrongTypingError) as e:
            ScheduledEvent(
                start_datetime=datetime(year=2000, month=1, day=1, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(year=2000, month=2, day=1, tzinfo=ZoneInfo("UTC")),
                expression=True,
            )
        self.assertEqual(
            "'ScheduledEvent.expression' expected ScheduleExpression if populated, got 'True' of "
            "type bool",
            str(e.exception),
        )

    def test_scheduled_event_invalid_schedule_method_raises(self):
        with self.assertRaises(StrongTypingError) as e:
            ScheduledEvent(
                start_datetime=datetime(year=2000, month=1, day=1, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(year=2000, month=2, day=1, tzinfo=ZoneInfo("UTC")),
                schedule_method=True,
            )
        self.assertEqual(
            "'ScheduledEvent.schedule_method' expected EndOfMonthSchedule if populated, got "
            "'True' of type bool",
            str(e.exception),
        )

    def test_scheduled_event_no_skip(self):
        start_datetime = datetime(year=2000, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end_datetime = datetime(year=2000, month=2, day=1, tzinfo=ZoneInfo("UTC"))
        schedule_expression = ScheduleExpression(day="5")

        scheduled_event = ScheduledEvent(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            expression=schedule_expression,
        )
        self.assertEqual(start_datetime, scheduled_event.start_datetime)
        self.assertEqual(end_datetime, scheduled_event.end_datetime)
        self.assertEqual(schedule_expression, scheduled_event.expression)

    def test_scheduled_event_invalid_skip_raises(self):
        with self.assertRaises(StrongTypingError) as e:
            ScheduledEvent(
                start_datetime=datetime(year=2000, month=1, day=1, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(year=2000, month=2, day=1, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(day="5"),
                skip="not-a-skip",
            )
        self.assertEqual(
            "'ScheduledEvent.skip' expected Union[bool, ScheduleSkip] if populated, got "
            "'not-a-skip' of type str",
            str(e.exception),
        )

    def test_scheduled_event_indefinite_skip(self):
        start_datetime = datetime(year=2000, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end_datetime = datetime(year=2000, month=2, day=1, tzinfo=ZoneInfo("UTC"))
        schedule_expression = ScheduleExpression(day="5")

        scheduled_event = ScheduledEvent(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            expression=schedule_expression,
            skip=True,
        )
        self.assertEqual(start_datetime, scheduled_event.start_datetime)
        self.assertEqual(end_datetime, scheduled_event.end_datetime)
        self.assertEqual(schedule_expression, scheduled_event.expression)
        self.assertEqual(True, scheduled_event.skip)

    def test_scheduled_event_unskip(self):
        start_datetime = datetime(year=2000, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        end_datetime = datetime(year=2000, month=2, day=1, tzinfo=ZoneInfo("UTC"))
        schedule_expression = ScheduleExpression(day="5")

        scheduled_event = ScheduledEvent(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            expression=schedule_expression,
            skip=False,
        )
        self.assertEqual(start_datetime, scheduled_event.start_datetime)
        self.assertEqual(end_datetime, scheduled_event.end_datetime)
        self.assertEqual(schedule_expression, scheduled_event.expression)
        self.assertEqual(False, scheduled_event.skip)

    def test_scheduled_event_from_proto_skips_validation(self):
        start_datetime = "not-datetime"
        end_datetime = 2022
        schedule_expression = True
        schedule_method = "not-end-of-month-schedule"

        scheduled_event = ScheduledEvent(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            expression=schedule_expression,
            schedule_method=schedule_method,
            _from_proto=True,
        )
        self.assertEqual(start_datetime, scheduled_event.start_datetime)
        self.assertEqual(end_datetime, scheduled_event.end_datetime)
        self.assertEqual(schedule_expression, scheduled_event.expression)

    def test_scheduled_event_not_exactly_one_of_expression_and_schedule_method_raises(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            ScheduledEvent(
                start_datetime=datetime(year=2000, month=1, day=1, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(year=2000, month=2, day=1, tzinfo=ZoneInfo("UTC")),
            )
        self.assertEqual(
            "ScheduledEvent must have exactly one of expression or schedule_method set",
            str(e.exception),
        )

    # EndOfMonthSchedule

    def test_end_of_month_schedule_type_default_values(self):
        end_of_month_schedule = EndOfMonthSchedule(day=1)
        self.assertEqual(0, end_of_month_schedule.hour)
        self.assertEqual(0, end_of_month_schedule.minute)
        self.assertEqual(0, end_of_month_schedule.second)
        self.assertEqual(ScheduleFailover.FIRST_VALID_DAY_BEFORE, end_of_month_schedule.failover)

    def test_end_of_month_schedule_type_can_set_values(self):
        end_of_month_schedule = EndOfMonthSchedule(
            day=15, hour=10, minute=20, second=5, failover=ScheduleFailover.FIRST_VALID_DAY_BEFORE
        )
        self.assertEqual(15, end_of_month_schedule.day)
        self.assertEqual(10, end_of_month_schedule.hour)
        self.assertEqual(20, end_of_month_schedule.minute)
        self.assertEqual(5, end_of_month_schedule.second)
        self.assertEqual(ScheduleFailover.FIRST_VALID_DAY_BEFORE, end_of_month_schedule.failover)

    def test_end_of_month_schedule_raise_if_values_out_of_range(self):
        values = [
            {"day": 0},
            {"day": 32},
            {"day": 1, "hour": -1},
            {"day": 1, "hour": 25},
            {"day": 1, "minute": -1},
            {"day": 1, "minute": 61},
            {"day": 1, "second": -1},
            {"day": 1, "second": 61},
        ]

        error_parts = [
            ("day", 1, 31),
            ("day", 1, 31),
            ("hour", 0, 23),
            ("hour", 0, 23),
            ("minute", 0, 59),
            ("minute", 0, 59),
            ("second", 0, 59),
            ("second", 0, 59),
        ]

        for i, value in enumerate(values):
            time_component, low, high = error_parts[i]
            with self.assertRaises(InvalidSmartContractError) as e:
                EndOfMonthSchedule(**value)
            self.assertEqual(
                str(e.exception),
                f"Argument {time_component} of EndOfMonthSchedule"
                f" object is out of range({low}-{high}).",
            )

    

    # SupervisedHooks

    def test_supervised_hooks(self):
        supervised_hooks = SupervisedHooks(pre_posting_hook=SupervisionExecutionMode.OVERRIDE)
        self.assertEqual(supervised_hooks.pre_posting_hook, SupervisionExecutionMode.OVERRIDE)

    def test_supervised_hooks_argument_required(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            SupervisedHooks()

        self.assertEqual(str(e.exception), "At least one hook supervision must be specified.")

    # Rejection

    def test_rejection(self):
        rejection = Rejection(message="Rejection", reason_code=RejectionReason.INSUFFICIENT_FUNDS)
        self.assertEqual("Rejection", rejection.message)
        self.assertEqual(RejectionReason.INSUFFICIENT_FUNDS, rejection.reason_code)

    def test_rejection_with_no_reason_code(self):
        rejection = Rejection(message="Rejection")
        self.assertEqual("Rejection", rejection.message)
        self.assertEqual(None, rejection.reason_code)

    def test_rejection_raises_with_no_message(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            Rejection(message="", reason_code=RejectionReason.INSUFFICIENT_FUNDS)
        self.assertEqual("Rejection 'message' must be populated", str(ex.exception))

    def test_rejection_from_proto_skips_validation(self):
        rejection = Rejection(message=True, _from_proto=True)
        self.assertEqual(True, rejection.message)
        self.assertEqual(None, rejection.reason_code)

    # Hook Results

    def test_derived_parameter_result(self):
        derived_parameters_result = DerivedParameterHookResult(
            parameters_return_value={
                "interest_account": "1",
                "repayment_date": datetime(2019, 12, 12, 13, 20),
                "denomination": "GBP",
                "monthly_repayment": Decimal("500.00"),
                "customer_name": "Paul",
                "tier": UnionItemValue(key="GOLD"),
                "interest_payment_day": OptionalValue(),
                "overdraft_limit": OptionalValue(Decimal("1000.00")),
                "overdraft_fee": OptionalValue(None),
            }
        )
        self.assertEqual(9, len(derived_parameters_result.parameters_return_value))

    def test_derived_parameter_result_raises_with_invalid_return_value(self):
        with self.assertRaises(StrongTypingError) as ex:
            DerivedParameterHookResult(parameters_return_value=None)
        self.assertEqual(
            "'parameters_return_value' expected dict, got None",
            str(ex.exception),
        )

    def test_deactivation_hook_result_without_directives_and_rejection(self):
        deactivation_hook_result = DeactivationHookResult()
        self.assertEqual([], deactivation_hook_result.account_notification_directives)
        self.assertEqual([], deactivation_hook_result.posting_instructions_directives)
        self.assertEqual(None, deactivation_hook_result.rejection)

    def test_deactivation_hook_result_with_directives(self):
        account_notification_directives = [
            AccountNotificationDirective(
                notification_type="test_notification_type",
                notification_details={"key1": "value1"},
            )
        ]
        custom_instructions = CustomInstruction(
            postings=[
                Posting(
                    amount=Decimal(1),
                    credit=True,
                    account_id="1",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    amount=Decimal(1),
                    credit=False,
                    account_id="2",
                    denomination="GBP",
                    account_address="TEST",
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ]
        )
        posting_instructions_directives = [
            PostingInstructionsDirective(
                posting_instructions=[custom_instructions],
                client_batch_id="international-payment",
                value_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
            )
        ]
        update_account_event_type_directives = [
            UpdateAccountEventTypeDirective(
                event_type="event_type_1",
                end_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
            )
        ]
        deactivation_hook_result = DeactivationHookResult(
            account_notification_directives=account_notification_directives,
            posting_instructions_directives=posting_instructions_directives,
            update_account_event_type_directives=update_account_event_type_directives,
        )
        self.assertEqual(
            account_notification_directives,
            deactivation_hook_result.account_notification_directives,
        )
        self.assertEqual(
            posting_instructions_directives,
            deactivation_hook_result.posting_instructions_directives,
        )
        self.assertEqual(
            update_account_event_type_directives,
            deactivation_hook_result.update_account_event_type_directives,
        )

    def test_deactivation_hook_result_with_rejection(self):
        rejection = Rejection(
            message="Cannot close account until loan repaid",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        deactivation_hook_result = DeactivationHookResult(rejection=rejection)
        self.assertEqual(rejection, deactivation_hook_result.rejection)

    def test_deactivation_hook_result_with_rejection_and_directives_errors(self):
        account_notification_directives = [
            AccountNotificationDirective(
                notification_type="test_notification_type",
                notification_details={"key1": "value1"},
            )
        ]
        custom_instructions = CustomInstruction(
            postings=[
                Posting(
                    amount=Decimal(1),
                    credit=True,
                    account_id="1",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    amount=Decimal(1),
                    credit=False,
                    account_id="2",
                    denomination="GBP",
                    account_address="TEST",
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ]
        )
        posting_instructions_directives = [
            PostingInstructionsDirective(posting_instructions=[custom_instructions])
        ]
        update_account_event_type_directives = [
            UpdateAccountEventTypeDirective(
                event_type="event_type_1",
                end_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
            )
        ]
        rejection = Rejection(
            message="Cannot close account until loan repaid",
            reason_code=RejectionReason.AGAINST_TNC,
        )
        with self.assertRaises(InvalidSmartContractError) as ex:
            DeactivationHookResult(
                account_notification_directives=account_notification_directives,
                posting_instructions_directives=posting_instructions_directives,
                update_account_event_type_directives=update_account_event_type_directives,
                rejection=rejection,
            )
        self.assertEqual(
            str(ex.exception),
            "DeactivationHookResult allows the population of directives or rejection, but not both",
        )

    def test_post_parameter_change_hook_result_without_directives(self):
        post_parameter_change_hook_result = PostParameterChangeHookResult()
        self.assertEqual([], post_parameter_change_hook_result.account_notification_directives)
        self.assertEqual([], post_parameter_change_hook_result.posting_instructions_directives)
        self.assertEqual([], post_parameter_change_hook_result.update_account_event_type_directives)

    def test_post_parameter_change_hook_result_with_directives(self):
        account_notification_directives = [
            AccountNotificationDirective(
                notification_type="test_notification_type",
                notification_details={"key1": "value1"},
            )
        ]
        custom_instructions = CustomInstruction(
            postings=[
                Posting(
                    amount=Decimal(1),
                    credit=True,
                    account_id="account_id",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    amount=Decimal(1),
                    credit=False,
                    account_id="2",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ]
        )
        posting_instructions_directives = [
            PostingInstructionsDirective(
                client_batch_id="international-payment",
                value_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
                posting_instructions=[custom_instructions],
            )
        ]
        update_account_event_type_directives = [
            UpdateAccountEventTypeDirective(
                event_type="event_type_1",
                end_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
            )
        ]
        post_parameter_change_hook_result = PostParameterChangeHookResult(
            account_notification_directives=account_notification_directives,
            posting_instructions_directives=posting_instructions_directives,
            update_account_event_type_directives=update_account_event_type_directives,
        )
        self.assertEqual(
            account_notification_directives,
            post_parameter_change_hook_result.account_notification_directives,
        )
        self.assertEqual(
            posting_instructions_directives,
            post_parameter_change_hook_result.posting_instructions_directives,
        )
        self.assertEqual(
            update_account_event_type_directives,
            post_parameter_change_hook_result.update_account_event_type_directives,
        )

    def test_post_posting_hook_result_without_directives(self):
        post_posting_hook_result = PostPostingHookResult()
        self.assertEqual([], post_posting_hook_result.account_notification_directives)
        self.assertEqual([], post_posting_hook_result.posting_instructions_directives)
        self.assertEqual([], post_posting_hook_result.update_account_event_type_directives)

    def test_post_posting_hook_result_with_directives(self):
        account_notification_directives = [
            AccountNotificationDirective(
                notification_type="test_notification_type",
                notification_details={"key1": "value1"},
            )
        ]
        custom_instructions = CustomInstruction(
            postings=[
                Posting(
                    amount=Decimal(1),
                    credit=True,
                    account_id="account_id",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    amount=Decimal(1),
                    credit=False,
                    account_id="2",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ]
        )
        posting_instructions_directives = [
            PostingInstructionsDirective(
                client_batch_id="international-payment",
                value_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
                posting_instructions=[custom_instructions],
            )
        ]
        update_account_event_type_directives = [
            UpdateAccountEventTypeDirective(
                event_type="event_type_1",
                end_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
            )
        ]
        post_posting_hook_result = PostPostingHookResult(
            account_notification_directives=account_notification_directives,
            posting_instructions_directives=posting_instructions_directives,
            update_account_event_type_directives=update_account_event_type_directives,
        )
        self.assertEqual(
            account_notification_directives,
            post_posting_hook_result.account_notification_directives,
        )
        self.assertEqual(
            posting_instructions_directives,
            post_posting_hook_result.posting_instructions_directives,
        )
        self.assertEqual(
            update_account_event_type_directives,
            post_posting_hook_result.update_account_event_type_directives,
        )

    def test_post_posting_hook_result_from_proto_skips_validation(self):
        post_posting_hook_result = PostPostingHookResult(
            update_account_event_type_directives=True, _from_proto=True
        )
        self.assertEqual(True, post_posting_hook_result.update_account_event_type_directives)

    def test_pre_parameter_change_hook_result(self):
        rejection = Rejection(message="Rejection", reason_code=RejectionReason.INSUFFICIENT_FUNDS)
        pre_parameter_change_hook_result = PreParameterChangeHookResult(rejection=rejection)
        self.assertEqual(rejection, pre_parameter_change_hook_result.rejection)

    def test_pre_parameter_change_hook_result_with_no_rejection(self):
        pre_parameter_change_hook_result = PreParameterChangeHookResult()
        self.assertEqual(None, pre_parameter_change_hook_result.rejection)

    def test_pre_parameter_change_hook_result_raises_with_invalid_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            PreParameterChangeHookResult(rejection=True)
        self.assertEqual(
            "'rejection' expected Rejection, got 'True' of type bool", str(ex.exception)
        )

    def test_pre_posting_hook_result(self):
        rejection = Rejection(message="Rejection", reason_code=RejectionReason.INSUFFICIENT_FUNDS)
        pre_posting_hook_result = PrePostingHookResult(rejection=rejection)
        self.assertEqual(rejection, pre_posting_hook_result.rejection)

    def test_pre_posting_hook_result_with_no_rejection(self):
        pre_posting_hook_result = PrePostingHookResult()
        self.assertEqual(None, pre_posting_hook_result.rejection)

    def test_pre_posting_hook_skips_validation(self):
        pre_posting_hook_result = PrePostingHookResult(rejection=True, _from_proto=True)
        self.assertEqual(True, pre_posting_hook_result.rejection)

    def test_post_activate_code_result_without_directives_or_return_values(self):
        post_activate_code_result = ActivationHookResult()
        self.assertEqual([], post_activate_code_result.account_notification_directives)
        self.assertEqual([], post_activate_code_result.posting_instructions_directives)
        self.assertEqual({}, post_activate_code_result.scheduled_events_return_value)

    def test_post_activate_code_result_with_directives_and_return_values(self):
        account_notification_directives = [
            AccountNotificationDirective(
                notification_type="test_notification_type",
                notification_details={"key1": "value1"},
            )
        ]
        custom_instructions = CustomInstruction(
            postings=[
                Posting(
                    amount=Decimal(1),
                    credit=True,
                    account_id="account_id",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    amount=Decimal(1),
                    credit=False,
                    account_id="2",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ]
        )
        posting_instructions_directives = [
            PostingInstructionsDirective(
                client_batch_id="international-payment",
                value_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
                posting_instructions=[custom_instructions],
            )
        ]
        scheduled_events_return_value = {
            "event_1": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(1970, 1, 1, second=2, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(
                    year="2000",
                    month="1",
                    day="1",
                    hour="0",
                    minute="0",
                    second="0",
                ),
                skip=ScheduleSkip(
                    end=datetime(1970, 1, 1, second=3, tzinfo=ZoneInfo("UTC")),
                ),
            ),
            "event_2": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=5, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(1970, 1, 1, second=6, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(
                    day_of_week="mon",
                ),
            ),
        }
        post_activate_code_result = ActivationHookResult(
            account_notification_directives=account_notification_directives,
            posting_instructions_directives=posting_instructions_directives,
            scheduled_events_return_value=scheduled_events_return_value,
        )
        self.assertEqual(
            account_notification_directives,
            post_activate_code_result.account_notification_directives,
        )
        self.assertEqual(
            posting_instructions_directives,
            post_activate_code_result.posting_instructions_directives,
        )
        self.assertEqual(
            scheduled_events_return_value,
            post_activate_code_result.scheduled_events_return_value,
        )

    def test_scheduled_event_hook_result_without_directives(self):
        scheduled_event_hook_result = ScheduledEventHookResult()
        self.assertEqual([], scheduled_event_hook_result.account_notification_directives)
        self.assertEqual([], scheduled_event_hook_result.posting_instructions_directives)
        self.assertEqual([], scheduled_event_hook_result.update_account_event_type_directives)

    def test_scheduled_event_hook_result_with_directives(self):
        account_notification_directives = [
            AccountNotificationDirective(
                notification_type="test_notification_type",
                notification_details={"key1": "value1"},
            )
        ]
        custom_instructions = CustomInstruction(
            postings=[
                Posting(
                    amount=Decimal(1),
                    credit=True,
                    account_id="account_id",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    amount=Decimal(1),
                    credit=False,
                    account_id="2",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ]
        )
        posting_instructions_directives = [
            PostingInstructionsDirective(
                client_batch_id="international-payment",
                value_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
                posting_instructions=[custom_instructions],
            )
        ]
        update_account_event_type_directives = [
            UpdateAccountEventTypeDirective(
                event_type="event_type_1",
                end_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
            )
        ]
        scheduled_event_hook_result = ScheduledEventHookResult(
            account_notification_directives=account_notification_directives,
            posting_instructions_directives=posting_instructions_directives,
            update_account_event_type_directives=update_account_event_type_directives,
        )
        self.assertEqual(
            account_notification_directives,
            scheduled_event_hook_result.account_notification_directives,
        )
        self.assertEqual(
            posting_instructions_directives,
            scheduled_event_hook_result.posting_instructions_directives,
        )
        self.assertEqual(
            update_account_event_type_directives,
            scheduled_event_hook_result.update_account_event_type_directives,
        )

    def test_scheduled_event_hook_result_from_proto_skips_validation(self):
        scheduled_event_hook_result = ScheduledEventHookResult(
            update_account_event_type_directives=True, _from_proto=True
        )
        self.assertEqual(True, scheduled_event_hook_result.update_account_event_type_directives)

    def test_supervisor_post_posting_hook_result_without_directives(self):
        supervisor_post_posting_hook_result = SupervisorPostPostingHookResult()
        self.assertEqual([], supervisor_post_posting_hook_result.plan_notification_directives)
        self.assertEqual([], supervisor_post_posting_hook_result.update_plan_event_type_directives)

        self.assertEqual(
            {}, supervisor_post_posting_hook_result.supervisee_account_notification_directives
        )
        self.assertEqual(
            {}, supervisor_post_posting_hook_result.supervisee_posting_instructions_directives
        )
        self.assertEqual(
            {}, supervisor_post_posting_hook_result.supervisee_update_account_event_type_directives
        )

    def test_supervisor_post_posting_hook_result_with_directives(self):
        plan_notification_directives = [
            PlanNotificationDirective(
                notification_type="test_notification_type",
                notification_details={"key1": "value1"},
            )
        ]
        update_plan_event_type_directives = [
            UpdatePlanEventTypeDirective(
                event_type="event_type",
                skip=True,
            )
        ]
        supervisee_account_notification_directives = {
            self.test_account_id: [
                AccountNotificationDirective(
                    notification_type="test_notification_type",
                    notification_details={"key1": "value1"},
                )
            ]
        }
        custom_instructions = CustomInstruction(
            postings=[
                Posting(
                    amount=Decimal(1),
                    credit=True,
                    account_id="account_id",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    amount=Decimal(1),
                    credit=False,
                    account_id="2",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ]
        )
        supervisee_posting_instructions_directives = {
            self.test_account_id: [
                PostingInstructionsDirective(
                    client_batch_id="international-payment",
                    value_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
                    posting_instructions=[custom_instructions],
                )
            ]
        }
        supervisee_update_account_event_type_directives = {
            self.test_account_id: [
                UpdateAccountEventTypeDirective(
                    event_type="event_type_1",
                    end_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
                )
            ]
        }

        supervisor_post_posting_hook_result = SupervisorPostPostingHookResult(
            plan_notification_directives=plan_notification_directives,
            update_plan_event_type_directives=update_plan_event_type_directives,
            supervisee_account_notification_directives=supervisee_account_notification_directives,
            supervisee_posting_instructions_directives=supervisee_posting_instructions_directives,  # noqa: E501
            supervisee_update_account_event_type_directives=supervisee_update_account_event_type_directives,  # noqa: E501
        )
        self.assertEqual(
            plan_notification_directives,
            supervisor_post_posting_hook_result.plan_notification_directives,
        )
        self.assertEqual(
            update_plan_event_type_directives,
            supervisor_post_posting_hook_result.update_plan_event_type_directives,
        )

        self.assertEqual(
            supervisee_account_notification_directives,
            supervisor_post_posting_hook_result.supervisee_account_notification_directives,
        )
        self.assertEqual(
            supervisee_posting_instructions_directives,
            supervisor_post_posting_hook_result.supervisee_posting_instructions_directives,
        )
        self.assertEqual(
            supervisee_update_account_event_type_directives,
            supervisor_post_posting_hook_result.supervisee_update_account_event_type_directives,
        )

    def test_supervisor_pre_posting_hook_result(self):
        rejection = Rejection(message="Rejection", reason_code=RejectionReason.INSUFFICIENT_FUNDS)
        supervisor_pre_posting_hook_result = SupervisorPrePostingHookResult(rejection=rejection)
        self.assertEqual(rejection, supervisor_pre_posting_hook_result.rejection)

    def test_supervisor_pre_posting_hook_result_with_no_rejection(self):
        supervisor_pre_posting_hook_result = SupervisorPrePostingHookResult()
        self.assertEqual(None, supervisor_pre_posting_hook_result.rejection)

    def test_supervisor_pre_posting_hook_raises_with_invalid_values(self):
        with self.assertRaises(StrongTypingError) as ex:
            SupervisorPrePostingHookResult(rejection=True)
        self.assertEqual(
            "'rejection' expected Rejection, got 'True' of type bool",
            str(ex.exception),
        )

    def test_supervisor_scheduled_event_hook_result_without_directives(self):
        supervisor_scheduled_event_hook_result = SupervisorScheduledEventHookResult()
        self.assertEqual([], supervisor_scheduled_event_hook_result.plan_notification_directives)
        self.assertEqual(
            [], supervisor_scheduled_event_hook_result.update_plan_event_type_directives
        )

        self.assertEqual(
            {}, supervisor_scheduled_event_hook_result.supervisee_account_notification_directives
        )
        self.assertEqual(
            {}, supervisor_scheduled_event_hook_result.supervisee_posting_instructions_directives
        )
        self.assertEqual(
            {},
            supervisor_scheduled_event_hook_result.supervisee_update_account_event_type_directives,
        )

    def test_supervisor_scheduled_event_hook_result_with_directives(self):
        plan_notification_directives = [
            PlanNotificationDirective(
                notification_type="test_notification_type",
                notification_details={"key1": "value1"},
            )
        ]
        update_plan_event_type_directives = [
            UpdatePlanEventTypeDirective(
                event_type="event_type",
                skip=True,
            )
        ]
        supervisee_account_notification_directives = {
            self.test_account_id: [
                AccountNotificationDirective(
                    notification_type="test_notification_type",
                    notification_details={"key1": "value1"},
                )
            ]
        }
        custom_instructions = CustomInstruction(
            postings=[
                Posting(
                    amount=Decimal(1),
                    credit=True,
                    account_id="account_id",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    amount=Decimal(1),
                    credit=False,
                    account_id="2",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ]
        )
        supervisee_posting_instructions_directives = {
            self.test_account_id: [
                PostingInstructionsDirective(
                    client_batch_id="international-payment",
                    value_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
                    posting_instructions=[custom_instructions],
                )
            ]
        }
        supervisee_update_account_event_type_directives = {
            self.test_account_id: [
                UpdateAccountEventTypeDirective(
                    event_type="event_type_1",
                    end_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
                )
            ]
        }

        supervisor_scheduled_event_hook_result = SupervisorScheduledEventHookResult(
            plan_notification_directives=plan_notification_directives,
            update_plan_event_type_directives=update_plan_event_type_directives,
            supervisee_account_notification_directives=supervisee_account_notification_directives,
            supervisee_posting_instructions_directives=supervisee_posting_instructions_directives,  # noqa: E501
            supervisee_update_account_event_type_directives=supervisee_update_account_event_type_directives,  # noqa: E501
        )
        self.assertEqual(
            plan_notification_directives,
            supervisor_scheduled_event_hook_result.plan_notification_directives,
        )
        self.assertEqual(
            update_plan_event_type_directives,
            supervisor_scheduled_event_hook_result.update_plan_event_type_directives,
        )

        self.assertEqual(
            supervisee_account_notification_directives,
            supervisor_scheduled_event_hook_result.supervisee_account_notification_directives,
        )
        self.assertEqual(
            supervisee_posting_instructions_directives,
            supervisor_scheduled_event_hook_result.supervisee_posting_instructions_directives,
        )
        self.assertEqual(
            supervisee_update_account_event_type_directives,
            supervisor_scheduled_event_hook_result.supervisee_update_account_event_type_directives,
        )

    def test_conversion_hook_result_without_directives_or_return_values(self):
        conversion_hook_result = ConversionHookResult()
        self.assertEqual([], conversion_hook_result.account_notification_directives)
        self.assertEqual([], conversion_hook_result.posting_instructions_directives)
        self.assertEqual({}, conversion_hook_result.scheduled_events_return_value)

    def test_conversion_hook_result_with_directives_and_return_values(self):
        account_notification_directives = [
            AccountNotificationDirective(
                notification_type="test_notification_type",
                notification_details={"key1": "value1"},
            )
        ]
        custom_instructions = CustomInstruction(
            postings=[
                Posting(
                    amount=Decimal(1),
                    credit=True,
                    account_id="account_id",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
                Posting(
                    amount=Decimal(1),
                    credit=False,
                    account_id="2",
                    denomination="GBP",
                    account_address=DEFAULT_ADDRESS,
                    asset=DEFAULT_ASSET,
                    phase=Phase.COMMITTED,
                ),
            ]
        )
        posting_instructions_directives = [
            PostingInstructionsDirective(
                client_batch_id="international-payment",
                value_datetime=datetime(2022, 3, 27, tzinfo=ZoneInfo("UTC")),
                posting_instructions=[custom_instructions],
            )
        ]
        scheduled_events_return_value = {
            "event_1": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=1, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(1970, 1, 1, second=2, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(
                    year="2000",
                    month="1",
                    day="1",
                    hour="0",
                    minute="0",
                    second="0",
                ),
                skip=ScheduleSkip(
                    end=datetime(1970, 1, 1, second=4, tzinfo=ZoneInfo("UTC")),
                ),
            ),
            "event_2": ScheduledEvent(
                start_datetime=datetime(1970, 1, 1, second=5, tzinfo=ZoneInfo("UTC")),
                end_datetime=datetime(1970, 1, 1, second=6, tzinfo=ZoneInfo("UTC")),
                expression=ScheduleExpression(
                    day_of_week="mon",
                ),
            ),
        }
        conversion_hook_result = ConversionHookResult(
            account_notification_directives=account_notification_directives,
            posting_instructions_directives=posting_instructions_directives,
            scheduled_events_return_value=scheduled_events_return_value,
        )
        self.assertEqual(
            account_notification_directives,
            conversion_hook_result.account_notification_directives,
        )
        self.assertEqual(
            posting_instructions_directives,
            conversion_hook_result.posting_instructions_directives,
        )
        self.assertEqual(
            scheduled_events_return_value,
            conversion_hook_result.scheduled_events_return_value,
        )

    def test_conversion_hook_result_raises_with_invalid_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            ConversionHookResult(account_notification_directives=True)
        expected = (
            "Expected list of AccountNotificationDirective objects for 'account_directives', got "
            "'True'"
        )
        self.assertEqual(expected, str(ex.exception))
        with self.assertRaises(StrongTypingError) as ex:
            ConversionHookResult(posting_instructions_directives=True)
        expected = (
            "Expected list of PostingInstructionsDirective objects for 'posting_directives', got "
            "'True'"
        )
        self.assertEqual(expected, str(ex.exception))
        with self.assertRaises(StrongTypingError) as ex:
            ConversionHookResult(scheduled_events_return_value=True)
        expected = "Expected dict, got 'True' of type bool"
        self.assertEqual(expected, str(ex.exception))

    # UpdatePlanEventTypeDirective

    def test_update_plan_event_type_directive_validation(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdatePlanEventTypeDirective(
                event_type="event_type_1",
                schedule_method=EndOfMonthSchedule(day=1),
                expression=ScheduleExpression(day="1"),
            )
        self.assertEqual(
            "UpdatePlanEventTypeDirective cannot contain both"
            " expression and schedule_method fields",
            str(ex.exception),
        )

    def test_update_plan_event_type_directive_invalid_constructor_arg_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            UpdatePlanEventTypeDirective(
                event_type="event_type",
                expression=1,  # EventTypeSchedule expected.
            )
        self.assertEquals("Expected ScheduleExpression, got '1' of type int", str(ex.exception))

    def test_update_plan_event_type_directive_raises_with_naive_skip_end_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdatePlanEventTypeDirective(
                event_type="event_type_1",
                skip=ScheduleSkip(end=self.test_naive_datetime),
            )
        self.assertEqual(
            "'end' of ScheduleSkip is not timezone aware.",
            str(ex.exception),
        )

    def test_update_plan_event_type_directive_raises_with_naive_end_datetime(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdatePlanEventTypeDirective(
                event_type="event_type_1",
                end_datetime=self.test_naive_datetime,
            )
        self.assertIn(
            "'end_datetime' of UpdatePlanEventTypeDirective is not timezone aware.",
            str(ex.exception),
        )

    def test_update_plan_event_type_directive(self):
        schedule_method = EndOfMonthSchedule(day=1)
        update_plan_event_type_directive = UpdatePlanEventTypeDirective(
            event_type="event_type_1",
            end_datetime=self.test_end_datetime,
            schedule_method=schedule_method,
            skip=True,
        )
        self.assertEqual("event_type_1", update_plan_event_type_directive.event_type)
        self.assertEqual(self.test_end_datetime, update_plan_event_type_directive.end_datetime)
        self.assertEqual(update_plan_event_type_directive.schedule_method, schedule_method)
        self.assertTrue(update_plan_event_type_directive.skip)

    def test_update_plan_event_type_directive_skip_false(self):
        update_plan_event_type_directive = UpdatePlanEventTypeDirective(
            event_type="event_type_1",
            end_datetime=self.test_end_datetime,
            skip=False,
        )
        self.assertEqual("event_type_1", update_plan_event_type_directive.event_type)
        self.assertEqual(self.test_end_datetime, update_plan_event_type_directive.end_datetime)
        self.assertFalse(update_plan_event_type_directive.skip)

    def test_update_plan_event_type_directive_schedule_skip(self):
        skip_end = datetime(year=2021, month=1, day=1, tzinfo=ZoneInfo("UTC"))
        update_plan_event_type_directive = UpdatePlanEventTypeDirective(
            event_type="event_type_1",
            end_datetime=self.test_end_datetime,
            skip=ScheduleSkip(end=skip_end),
        )
        self.assertEqual("event_type_1", update_plan_event_type_directive.event_type)
        self.assertEqual(self.test_end_datetime, update_plan_event_type_directive.end_datetime)
        self.assertIsNotNone(update_plan_event_type_directive.skip)
        self.assertEqual(skip_end, update_plan_event_type_directive.skip.end)

    def test_update_plan_event_type_directive_raises_with_no_end_datetime_or_schedule(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            UpdatePlanEventTypeDirective(
                event_type="event_type_1",
            )

        self.assertIn(
            ("UpdatePlanEventTypeDirective object has to have either an end_datetime, an "),
            str(ex.exception),
        )

    def test_update_plan_event_type_directive_raises_with_invalid_skip_attribute(self):
        with self.assertRaises(StrongTypingError) as ex:
            UpdatePlanEventTypeDirective(
                event_type="event_type_1",
                end_datetime=self.test_end_datetime,
                skip="not_valid",
            )
        self.assertEquals(
            "'skip' expected Optional[Union[bool, ScheduleSkip]], got 'not_valid' of type str",
            str(ex.exception),
        )

    # SmartContractDescriptor

    def test_smart_contract_descriptor(self):
        supervised_smart_contract = SmartContractDescriptor(
            alias="test1",
            smart_contract_version_id="test_smart_contract_version_id",
            supervise_post_posting_hook=True,
        )
        self.assertEqual("test1", supervised_smart_contract.alias)

    def test_smart_contract_descriptor_raises_if_alias_not_populated(self):
        with self.assertRaises(StrongTypingError) as ex:
            SmartContractDescriptor(
                alias=None, smart_contract_version_id="test_smart_contract_version_id"
            )
        self.assertIn("SmartContractDescriptor 'alias' must be populated", str(ex.exception))

    def test_smart_contract_descriptor_raises_if_smart_contract_version_id_not_populated(self):
        with self.assertRaises(StrongTypingError) as ex:
            SmartContractDescriptor(alias="alias", smart_contract_version_id=None)
        self.assertIn(
            "SmartContractDescriptor 'smart_contract_version_id' must be populated",
            str(ex.exception),
        )

    def test_smart_contract_descriptor_no_supervised_hooks(self):
        supervised_smart_contract = SmartContractDescriptor(
            alias="test1", smart_contract_version_id="test_smart_contract_version_id"
        )
        self.assertEqual("test1", supervised_smart_contract.alias)
        self.assertIsNone(supervised_smart_contract.supervised_hooks)

    def test_smart_contract_descriptor_raises_with_invalid_supervised_hooks_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            SmartContractDescriptor(
                alias="test1",
                smart_contract_version_id="test_smart_contract_version_id",
                supervised_hooks="foo",
            )
        self.assertIn(
            "'SmartContractDescriptor.supervised_hooks' expected SupervisedHooks if populated, got "
            "'foo' of type str",
            str(ex.exception),
        )

    # SupervisedHooks

    def test_smart_contract_descriptor_supervised_hooks(self):
        supervised_hooks = SupervisedHooks(pre_posting_hook=SupervisionExecutionMode.OVERRIDE)
        supervised_smart_contract = SmartContractDescriptor(
            alias="test1",
            smart_contract_version_id="test_smart_contract_version_id",
            supervised_hooks=supervised_hooks,
        )
        self.assertEqual("test1", supervised_smart_contract.alias)
        self.assertEqual(supervised_hooks, supervised_smart_contract.supervised_hooks)

    # OptionalShape

    def test_can_construct_optional_shape(self):
        inner_shape = NumberShape()
        optional_shape = OptionalShape(shape=inner_shape)

        self.assertEqual(inner_shape, optional_shape.shape)

    def test_optional_shape_requires_shape_arg(self):
        with self.assertRaises(TypeError):
            OptionalShape()

    # Parameter

    def test_can_construct_parameter(self):
        shape = NumberShape()
        parameter = Parameter(
            name="name",
            description="description",
            display_name="display_name",
            level=ParameterLevel.INSTANCE,
            default_value=42,
            shape=shape,
        )

        self.assertEqual("name", parameter.name)
        self.assertEqual("description", parameter.description)
        self.assertEqual("display_name", parameter.display_name)
        self.assertEqual(ParameterLevel.INSTANCE, parameter.level)
        self.assertEqual(42, parameter.default_value)
        self.assertEqual(shape, parameter.shape)

    # BalancesFilter

    def test_balances_filter(self):
        addresses = ["CUSTOM_ADDRESS", "DEFAULT_ADDRESS"]
        balances_filter = BalancesFilter(addresses=addresses)
        self.assertEqual(addresses, balances_filter.addresses)

    def test_balances_filter_raises_with_empty_addresses(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesFilter(addresses=[])
        self.assertEqual(str(e.exception), "'addresses' must be a non empty list, got []")

    def test_balances_filter_raises_with_empty_address_field(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesFilter()
        self.assertEqual(str(e.exception), "'addresses' must be a non empty list, got []")

    def test_balances_filter_raises_with_addresses_invalid_element_type(self):
        with self.assertRaises(StrongTypingError) as e:
            BalancesFilter(addresses=[None])
        self.assertEqual(str(e.exception), "Expected List[str], got None")

    def test_balances_filter_raises_with_duplicate_addresses(self):
        with self.assertRaises(InvalidSmartContractError) as e:
            BalancesFilter(addresses=["address_1", "address_1"])
        self.assertEqual(
            str(e.exception), "BalancesFilter addresses must not contain any duplicate addresses."
        )

    def test_balances_filter_raises_invalid_argument_type(self):
        with self.assertRaises(StrongTypingError):
            BalancesFilter(addresses=123)

    # SmartContractEventType

    def test_smart_contract_event_type_can_be_created(self):
        event_type = SmartContractEventType(name="name", scheduler_tag_ids=["TAG"])
        self.assertEqual(event_type.name, "name")
        self.assertEqual(event_type.scheduler_tag_ids, ["TAG"])

    def test_smart_contract_event_type_when_name_empty(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            SmartContractEventType(name="", scheduler_tag_ids=["TAG"])
        self.assertIn("SmartContractEventType 'name' must be populated", str(ex.exception))

    def test_smart_contract_event_type_when_scheduler_tag_ids_invalid(self):
        with self.assertRaises(StrongTypingError) as ex:
            SmartContractEventType(name="name", scheduler_tag_ids="invalid")
        self.assertIn(
            "Expected list of str objects for 'scheduler_tag_ids', got 'invalid'", str(ex.exception)
        )

    # SupervisorContractEventType

    def test_supervisor_contract_event_type_can_be_created(self):
        event_type_name = "TEST_EVENT_1"
        scheduler_tag_ids = ["TEST_TAG_1", "TEST_TAG_2"]
        overrides_event_types = [
            ("S1", "TEST_EVENT_2"),
            ("S2", "TEST_EVENT_3"),
        ]

        event_type = SupervisorContractEventType(
            name=event_type_name,
            scheduler_tag_ids=scheduler_tag_ids,
            overrides_event_types=overrides_event_types,
        )

        self.assertEqual(event_type_name, event_type.name)
        self.assertEqual(scheduler_tag_ids, event_type.scheduler_tag_ids)
        self.assertEqual(overrides_event_types, event_type.overrides_event_types)

    def test_supervisor_contract_event_type_when_name_empty(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            SupervisorContractEventType(name="", scheduler_tag_ids=["TAG"])
        self.assertIn("SupervisorContractEventType 'name' must be populated", str(ex.exception))

    def test_supervisor_contract_event_type_when_scheduler_tag_ids_invalid(self):
        with self.assertRaises(StrongTypingError) as ex:
            SupervisorContractEventType(name="name", scheduler_tag_ids="invalid")
        self.assertIn(
            "Expected list of str objects for 'scheduler_tag_ids', got 'invalid'", str(ex.exception)
        )

    def test_supervisor_contract_event_type_when_scheduler_tag_ids_invalid_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            SupervisorContractEventType(name="name", scheduler_tag_ids=["TAG", 5])
        self.assertIn("Expected str, got '5'", str(ex.exception))

    def test_supervisor_contract_event_type_when_overrides_event_types_invalid(self):
        with self.assertRaises(StrongTypingError) as ex:
            SupervisorContractEventType(
                name="name", scheduler_tag_ids=["TAG"], overrides_event_types="invalid"
            )
        self.assertIn(
            "Expected list of Tuple[str, str] objects for 'overrides_event_types', got "
            "'invalid'",
            str(ex.exception),
        )

    def test_supervisor_contract_event_type_when_overrides_event_types_invalid_type(self):
        with self.assertRaises(StrongTypingError) as ex:
            SupervisorContractEventType(
                name="name",
                scheduler_tag_ids=["TAG"],
                overrides_event_types=[("S1", "TEST_EVENT_1"), 5],
            )
        self.assertIn("Expected Tuple[str, str], got '5'", str(ex.exception))

    # AddressDetails

    def test_address_details(self):
        address_details = AddressDetails(
            account_address="DEFAULT", description="Some desc", tags=["one", "two"]
        )

        self.assertEqual("DEFAULT", address_details.account_address)
        self.assertEqual("Some desc", address_details.description)
        self.assertEqual(["one", "two"], address_details.tags)

    def test_address_details_equality(self):
        default = AddressDetails(
            account_address="DEFAULT", description="Default address", tags=["default"]
        )
        other_default = AddressDetails(
            account_address="DEFAULT", description="Default address", tags=["default"]
        )
        self.assertEqual(default, other_default)

    def test_address_details_raises_with_no_address(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            AddressDetails(account_address=None, description="Some desc", tags=["one", "two"])
        self.assertEqual("AddressDetails 'account_address' must be populated", str(ex.exception))

    def test_address_details_raises_with_no_description(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            AddressDetails(account_address="DEFAULT", description=None, tags=["one", "two"])
        self.assertEqual("AddressDetails 'description' must be populated", str(ex.exception))

    def test_address_details_raises_with_no_tags(self):
        with self.assertRaises(InvalidSmartContractError) as ex:
            AddressDetails(account_address="DEFAULT", description="Some desc", tags=None)
        self.assertEqual("AddressDetails 'tags' must be populated", str(ex.exception))

    def test_address_details_raises_with_invalid_tags(self):
        with self.assertRaises(StrongTypingError) as ex:
            AddressDetails(account_address="DEFAULT", description="Some desc", tags=False)
        self.assertEqual("'tags' expected list, got 'False' of type bool", str(ex.exception))

    def test_address_details_skips_validation(self):
        address = AddressDetails(
            account_address="foo", description=None, tags=None, _from_proto=True
        )
        self.assertEqual("foo", address.account_address)

    # Logger

    def test_logger_debug_to_stderr(self):
        logger = Logger.instance()

        with StringIO() as buf:
            with redirect_stderr(buf):
                logger.debug("hello from the tside")

            self.assertEqual("hello from the tside", buf.getvalue().strip())

    def test_logger_raises_on_init(self):
        with self.assertRaises(Exception) as ex:
            Logger()
        self.assertEqual("Logger is a singleton. Use instance() instead.", str(ex.exception))

    # Data Fetcher Decorators
    fetcher_decorator_error = "decorator should not pass anything to hook"

    def test_requires_decorator(self):
        @requires(
            balances="latest",
            calendar=["cal_1"],
            data_scope="all",
            event_type="EVENT",
            flags=True,
            last_execution_datetime=["EVENT"],
            parameters=True,
            postings=True,
        )
        def hook(*args, **kwargs):
            self.assertEqual(args, (), self.fetcher_decorator_error)
            self.assertEqual(kwargs, {}, self.fetcher_decorator_error)

        hook()

    def test_fetch_account_data_decorator(self):
        @fetch_account_data(
            balances=["fetcher_1"],
            event_type="EVENT",
            
            postings=["fetcher_3"],
        )
        def hook(*args, **kwargs):
            self.assertEqual(args, (), self.fetcher_decorator_error)
            self.assertEqual(kwargs, {}, self.fetcher_decorator_error)

        hook()


class TestClientTransactionsDunderEq(TestCase):
    test_account_id = "123456"
    posting_datetime = datetime(2019, 12, 12, tzinfo=ZoneInfo("UTC"))

    def _create_uniform_client_transaction(self) -> ClientTransaction:
        pi_committed_postings = [
            Posting(
                account_id=self.test_account_id,
                account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                credit=False,
                phase=Phase.COMMITTED,
                amount=Decimal(10),
                denomination="GBP",
            ),
        ]
        pi = Transfer(
            debtor_target_account_id=self.test_account_id,
            creditor_target_account_id="1",
            amount=Decimal(10),
            denomination="GBP",
        )
        pi._set_output_attributes(  # noqa: SLF001
            insertion_datetime=self.posting_datetime,
            value_datetime=self.posting_datetime,
            client_batch_id="client_batch_id",
            batch_id="batch_id",
            committed_postings=pi_committed_postings,
            instruction_id="instruction_id",
            unique_client_transaction_id="CoreContracts_out",
        )
        client_transaction = ClientTransaction(
            client_transaction_id="ctxid",
            account_id=self.test_account_id,
            posting_instructions=[pi],
            tside=Tside.LIABILITY,
        )
        return client_transaction

    def test_instances_are_equal_by_value(self):
        transaction_1 = self._create_uniform_client_transaction()
        transaction_2 = self._create_uniform_client_transaction()
        self.assertNotEqual(id(transaction_1), id(transaction_2))
        self.assertEqual(transaction_1, transaction_2)

    def test_instances_are_not_equal_different_postings(self):
        transaction_1 = self._create_uniform_client_transaction()
        transaction_2 = self._create_uniform_client_transaction()
        transaction_1.posting_instructions[0].amount = Decimal(10)
        transaction_2.posting_instructions[0].amount = Decimal(45789)
        self.assertNotEqual(transaction_1, transaction_2)

    def test_instances_are_not_equal_different_tside(self):
        transaction_1 = self._create_uniform_client_transaction()
        transaction_2 = self._create_uniform_client_transaction()
        transaction_1.tside = Tside.LIABILITY
        transaction_2.tside = Tside.ASSET
        self.assertNotEqual(transaction_1, transaction_2)

    def test_attributes_that_are_compared(self):
        """Check that there are no additional attributes in the class that the __eq__ method does
        not check against.
        """
        expected_public_attributes = {
            "client_transaction_id",
            "account_id",
            "posting_instructions",
            "tside",
        }
        transaction = self._create_uniform_client_transaction()
        actual_public_attributes = {i for i in transaction.__dict__.keys() if i[:1] != "_"}
        self.assertEqual(actual_public_attributes, expected_public_attributes)  #
