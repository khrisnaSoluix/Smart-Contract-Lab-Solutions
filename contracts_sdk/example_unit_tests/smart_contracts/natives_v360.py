api = "3.6.0"
tside = Tside.ASSET
supported_denominations = ["GBP"]

CustomType = Type[int]
CustomNewType = NewType("CustomNewType", str)


def post_activate_code() -> NewType:
    _type_hint_helper(
        any_arg="Any",
        callable_arg=_func_callable,
        default_dict_arg=BalanceDefaultDict(lambda *_: Balance()),
        dict_arg={1: "a"},
        iterable_arg=[],
        iterator_arg=iter([]),
        list_arg=["a", "b", "c"],
        mapping_arg={"a": "b"},
        named_tuple_arg=vault,
        set_arg={"a", "b"},
        tuple_arg=(1, 2),
        type_arg=int,
        union_arg="a",
        optional_arg=[1, 2, 3],
    )
    return CustomNewType("all native types successfully processed")


# This hook demonstrates the use of native vault objects within Smart Contracts.
def derived_parameters(effective_date):
    checking_math_sqrt = math.sqrt(100)
    checking_math_ceil = math.ceil(100.2)

    interest = Decimal(12912.476)  # Arbitary interest amount
    repayment_date = datetime(2020, 1, 17) - timedelta(days=1)
    date_from_parser = parse_to_datetime("05.01.2015")

    interest_due_round_half_down = interest.quantize(Decimal(".01"), rounding=ROUND_HALF_DOWN)
    interest_due_round_half_up = interest.quantize(Decimal(".1"), rounding=ROUND_HALF_UP)
    interest_due_round_floor = interest.quantize(Decimal(".1"), rounding=ROUND_FLOOR)
    interest_due_round_down = interest.quantize(Decimal(".01"), rounding=ROUND_DOWN)
    interest_due_round_half_even = interest.quantize(Decimal(".01"), rounding=ROUND_HALF_EVEN)
    interest_due_round_05up = interest.quantize(Decimal(".1"), rounding=ROUND_05UP)
    interest_due_round_ceil = interest.quantize(Decimal(".1"), rounding=ROUND_CEILING)

    repayment_day = calendar.day_name[0]

    internal_account_balance = defaultdict(int)
    internal_account_balance["account 1"] = 20

    balances = vault.get_parameter_timeseries(name="balance_pot").latest()
    balance_dict = json_loads(balances)

    return {
        "interest_due_round_half_down": interest_due_round_half_down,
        "interest_due_round_half_up": interest_due_round_half_up,
        "interest_due_round_floor": interest_due_round_floor,
        "interest_due_round_down": interest_due_round_down,
        "interest_due_round_half_even": interest_due_round_half_even,
        "interest_due_round_05up": interest_due_round_05up,
        "interest_due_round_ceil": interest_due_round_ceil,
        "repayment_date": repayment_date,
        "date_from_parser": date_from_parser,
        "repayment_day": repayment_day,
        "internal_account_balance": internal_account_balance,
        "balance_dict": balance_dict["time 1"],
        "checking_math_sqrt": checking_math_sqrt,
        "checking_math_ceil": checking_math_ceil,
    }


def _type_hint_helper(
    any_arg: Any,
    callable_arg: Callable[[str], str],
    default_dict_arg: DefaultDict[str, Decimal],
    dict_arg: Dict[Decimal, str],
    iterable_arg: Iterable,
    iterator_arg: Iterator,
    list_arg: List[str],
    mapping_arg: Mapping[str, str],
    named_tuple_arg: NamedTuple,
    set_arg: Set[str],
    tuple_arg: Tuple[int],
    type_arg: CustomType,
    union_arg: Union[Decimal, str],
    optional_arg: Optional[int] = None,
) -> NoReturn:
    pass


def _func_callable(callable_arg: str) -> str:
    return ""


# flake8: noqa
