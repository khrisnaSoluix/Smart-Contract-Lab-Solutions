# Copyright @ 2021 Thought Machine Group Limited. All rights reserved.
"""
Fees Module
"""

api = "3.9.0"
display_name = "Fees Module"
description = "Set of functions for handling maintenance and transactional fees in smart contracts"

InactivityFeeDetails = NamedTuple(
    "InactivityFeeDetails",
    [
        ("fee_type", str),
        ("amount", Decimal),
        ("denomination", str),
        ("internal_account", str),
        ("is_account_dormant", bool),
    ],
)

MinBalanceFeeDetails = NamedTuple(
    "MinBalanceFeeDetails",
    [
        ("fee_type", str),
        ("amount", Decimal),
        ("denomination", str),
        ("internal_account", str),
        ("is_account_dormant", bool),
        ("account_creation_date", datetime),
        ("addresses", List[str]),
        ("minimum_balance_threshold", Decimal),
    ],
)

MaintenanceFeeDetails = NamedTuple(
    "MaintenanceFeeDetails",
    [
        ("fee_type", str),
        ("amount", Decimal),
        ("denomination", str),
        ("internal_account", str),
        ("is_account_dormant", bool),
        ("account_creation_date", datetime),
        ("addresses", List[str]),
        ("minimum_balance_threshold", Decimal),
        ("minimum_deposit", Decimal),
        ("waive_fee_if_mean_balance_above_threshold", bool),
        ("waive_fee_based_on_monthly_deposits", bool),
        ("included_transaction_types", List[str]),
        ("excluded_transaction_types", List[str]),
        ("client_transactions", Dict[Tuple[str, str], ClientTransaction]),
    ],
)


def construct_account_inactivity_fee_details(
    amount: Decimal,
    denomination: str,
    internal_account: str,
    is_account_dormant: bool = False,
) -> InactivityFeeDetails:

    return InactivityFeeDetails(
        fee_type="account_inactivity_fee",
        amount=amount,
        denomination=denomination,
        internal_account=internal_account,
        is_account_dormant=is_account_dormant,
    )


def construct_minimum_balance_fee_details(
    amount: Decimal,
    denomination: str,
    internal_account: str,
    is_account_dormant: bool = False,
    account_creation_date: datetime = None,
    addresses: List[str] = None,
    minimum_balance_threshold: Decimal = Decimal("0"),
) -> MinBalanceFeeDetails:

    return MinBalanceFeeDetails(
        fee_type="minimum_balance_fee",
        amount=amount,
        denomination=denomination,
        internal_account=internal_account,
        is_account_dormant=is_account_dormant,
        account_creation_date=account_creation_date,
        addresses=addresses or [DEFAULT_ADDRESS],
        minimum_balance_threshold=minimum_balance_threshold,
    )


def construct_maintenance_fee_details(
    fee_frequency: str,
    amount: Decimal,
    denomination: str,
    internal_account: str,
    is_account_dormant: bool = False,
    account_creation_date: datetime = None,
    addresses: List[str] = None,
    minimum_balance_threshold: Decimal = Decimal("0"),
    minimum_deposit: Decimal = Decimal("0"),
    waive_fee_if_mean_balance_above_threshold: bool = False,
    waive_fee_based_on_monthly_deposits: bool = False,
    included_transaction_types: List[str] = None,
    excluded_transaction_types: List[str] = None,
    client_transactions: Dict[Tuple[str, str], ClientTransaction] = None,
) -> MaintenanceFeeDetails:

    fee_type = "monthly_maintenance_fee" if fee_frequency == "monthly" else "annual_maintenance_fee"

    return MaintenanceFeeDetails(
        fee_type=fee_type,
        amount=amount,
        denomination=denomination,
        internal_account=internal_account,
        is_account_dormant=is_account_dormant,
        account_creation_date=account_creation_date,
        addresses=addresses or [DEFAULT_ADDRESS],
        minimum_balance_threshold=minimum_balance_threshold,
        minimum_deposit=minimum_deposit,
        waive_fee_if_mean_balance_above_threshold=waive_fee_if_mean_balance_above_threshold,
        waive_fee_based_on_monthly_deposits=waive_fee_based_on_monthly_deposits,
        included_transaction_types=included_transaction_types or [],
        excluded_transaction_types=excluded_transaction_types or [],
        client_transactions=client_transactions or {},
    )


def apply_multiple_fees(
    vault,
    effective_date: datetime,
    fees: List[Union[InactivityFeeDetails, MinBalanceFeeDetails, MaintenanceFeeDetails]],
    balances: BalanceTimeseries,
) -> List[PostingInstruction]:
    """
    Applies multiple fees to the account by looping through a list of fee_details Namedtuples

    :param effective_date: date and time of hook being run
    :param fees: List of fee_details, contructed by the constructor methods
    :param balances: current balances of the account

    :return: List of posting instructions
    """
    posting_ins = []

    for fee_details in fees:
        if (
            fee_details.fee_type == "monthly_maintenance_fee"
            or fee_details.fee_type == "annual_maintenance_fee"
        ):
            posting_ins.extend(apply_maintenance_fee(vault, effective_date, fee_details, balances))

        elif fee_details.fee_type == "minimum_balance_fee":
            posting_ins.extend(
                apply_minimum_balance_fee(vault, effective_date, fee_details, balances)
            )

        elif fee_details.fee_type == "account_inactivity_fee":
            posting_ins.extend(apply_inactivity_fee(vault, fee_details))

    return posting_ins


def apply_inactivity_fee(vault, fee_details: InactivityFeeDetails) -> List[PostingInstruction]:
    """
    Applies inactivity fee to the account, the fee may be waived if the account is active

    :param fee_details: InactivityFeeDetails
        InactivityFeeDetails attributes:
            amount: value of the fee
            denomination: the denomination the posting instructions will be in
            internal_account: internal account to make the posting to
            is_account_dormant: value of the dormancy flag, if the account has one

    :return: List of posting instructions
    """

    if fee_details.is_account_dormant and fee_details.amount > 0:
        return vault.make_internal_transfer_instructions(
            amount=fee_details.amount,
            denomination=fee_details.denomination,
            from_account_id=vault.account_id,
            from_account_address=DEFAULT_ADDRESS,
            to_account_id=fee_details.internal_account,
            to_account_address=DEFAULT_ADDRESS,
            asset=DEFAULT_ASSET,
            override_all_restrictions=True,
            client_transaction_id=f"INTERNAL_POSTING_APPLY_ACCOUNT_INACTIVITY_FEE"
            f"_{vault.get_hook_execution_id()}"
            f"_{fee_details.denomination}",
            instruction_details={
                "description": "Account inactivity fee",
                "event": "APPLY_ACCOUNT_INACTIVITY_FEE",
            },
        )

    return []


def apply_minimum_balance_fee(
    vault,
    effective_date,
    minimum_balance_fee_details: MinBalanceFeeDetails,
    balances: BalanceTimeseries,
) -> List[PostingInstruction]:
    """
    Applies a minimum balance fee to the account
    The minimum balance fee may be waived if any of the following criteria are met:
    1) The monthly mean balance is above the min balance threshold
    2) The account is dormant

    :param effective_date: datetime at which the fee is being applied
    :param minimum_balance_fee_details: Details used to determine whether minimum balance fee
        should be applied

        MinBalanceFeeDetails - attributes:
            amount: value of the fee
            denomination: the denomination the posting instructions will be in
            internal_account: internal account to make the posting to
            is_account_dormant: value of the dormancy flag, if the account has one
            account_creation_date: utc account creation date
            addresses: list of addresses to sample and combine the balance for calculating the
                monthly mean balance
            minimum_balance_threshold: the min balance limit that the account needs to have in order
                for the fee to be waived

    :param balances: current balances of the account

    :return: List of posting instructions
    """

    if (
        not minimum_balance_fee_details.is_account_dormant
        and minimum_balance_fee_details.amount > 0
    ):
        monthly_mean_balance = get_monthly_mean_balance(
            denomination=minimum_balance_fee_details.denomination,
            effective_date=effective_date,
            creation_date=minimum_balance_fee_details.account_creation_date,
            balances=balances,
            addresses=minimum_balance_fee_details.addresses,
        )
        if (
            monthly_mean_balance is None
            or monthly_mean_balance < minimum_balance_fee_details.minimum_balance_threshold
        ):
            return vault.make_internal_transfer_instructions(
                amount=minimum_balance_fee_details.amount,
                denomination=minimum_balance_fee_details.denomination,
                from_account_id=vault.account_id,
                from_account_address=DEFAULT_ADDRESS,
                to_account_id=minimum_balance_fee_details.internal_account,
                to_account_address=DEFAULT_ADDRESS,
                asset=DEFAULT_ASSET,
                override_all_restrictions=True,
                client_transaction_id="INTERNAL_POSTING_APPLY_MINIMUM_BALANCE_FEE"
                f"_{vault.get_hook_execution_id()}"
                f"_{minimum_balance_fee_details.denomination}",
                instruction_details={
                    "description": "Minimum balance fee",
                    "event": "APPLY_MINIMUM_BALANCE_FEE",
                },
            )
    return []


def apply_maintenance_fee(
    vault,
    effective_date: datetime,
    maintenance_fee_details: MaintenanceFeeDetails,
    balances: BalanceTimeseries,
) -> List[PostingInstruction]:
    """
    Generates postings for the application of account maintenance fees

    The maintenance fees may be waived if any of the following criteria are met:
    1) The account is dormant
    2) The monthly mean balance is above the min balance threshold only if the
    waive_fee_if_mean_balance_above_threshold flag is set to true
    3) A minimum required deposit is sent to the function and the sum of last month's transactions
    is higher than that minimum required deposit
    4) There are deposits made into the account in the last month and the
    waive_fee_based_on_monthly_deposits flag is set to true

    :param effective_date: datetime at which the fee is being applied
    :param maintenance_fee_details: Details used to determine whether maintenance fee
        should be applied

        MaintenanceFeeDetails - attributes:
            name: name of the maintenance fee, e.g. annual_maintenance_fee or
                monthly_maintenance_fee
            amount: value of the fee
            denomination: the denomination the posting instructions will be in
            internal_account: internal account to make the posting to
            is_account_dormant: value of the dormancy flag, if the account has one
            account_creation_date: utc account creation date
            addresses: list of addresses to sample and combine the balance for calculating the
                monthly mean balance
            minimum_balance_threshold: the min balance limit that the account needs to have in order
                for the fee to be waived
            minimum_deposit: the minimum required deposit value for the account
            waive_fee_if_mean_balance_above_threshold: flag to enable the waiving of the
                maintenance fee based on the minimum balance threshold (used for US checking
                account)
            waive_fee_based_on_monthly_deposits: flag to enable the waiving of the maintenance fee
                based on the number of monthly deposits made (used for US savings account)
            included_transaction_types: a list of tags that can be found inside a client transaction
                id, which can be used to filter in the transactions of the previous month
            excluded_transaction_types: a list of tags that can be found inside a client transaction
                id, which can be used to filter out the transactions of the previous month
            client_transactions: a map of (client_id, client_transaction_id) to a ClientTransaction

    :param balances: current balances of the account

    :return: List of posting instructions
    """

    if maintenance_fee_details.is_account_dormant or maintenance_fee_details.amount <= 0:
        return []

    if maintenance_fee_details.waive_fee_if_mean_balance_above_threshold:
        monthly_mean_balance = get_monthly_mean_balance(
            denomination=maintenance_fee_details.denomination,
            effective_date=effective_date,
            creation_date=maintenance_fee_details.account_creation_date,
            balances=balances,
            addresses=maintenance_fee_details.addresses,
        )
        if (
            monthly_mean_balance is not None
            and monthly_mean_balance >= maintenance_fee_details.minimum_balance_threshold
        ):
            return []

    if maintenance_fee_details.minimum_deposit:
        if (
            sum(
                get_previous_month_transaction_values_of_type(
                    effective_date,
                    maintenance_fee_details.denomination,
                    maintenance_fee_details.client_transactions,
                    maintenance_fee_details.account_creation_date,
                    types_excluded=maintenance_fee_details.excluded_transaction_types,
                )
            )
            >= maintenance_fee_details.minimum_deposit
        ):
            return []

    if maintenance_fee_details.waive_fee_based_on_monthly_deposits:
        if (
            len(
                get_previous_month_transaction_values_of_type(
                    effective_date,
                    maintenance_fee_details.denomination,
                    maintenance_fee_details.client_transactions,
                    maintenance_fee_details.account_creation_date,
                    types_included=maintenance_fee_details.included_transaction_types,
                )
            )
            > 0
        ):
            return []

    return vault.make_internal_transfer_instructions(
        amount=maintenance_fee_details.amount,
        denomination=maintenance_fee_details.denomination,
        from_account_id=vault.account_id,
        from_account_address=DEFAULT_ADDRESS,
        to_account_id=maintenance_fee_details.internal_account,
        to_account_address=DEFAULT_ADDRESS,
        asset=DEFAULT_ASSET,
        override_all_restrictions=True,
        client_transaction_id=f"INTERNAL_POSTING_APPLY_{maintenance_fee_details.fee_type.upper()}"
        f"_{vault.get_hook_execution_id()}"
        f"_{maintenance_fee_details.denomination}",
        instruction_details={
            "description": f'{maintenance_fee_details.fee_type.capitalize().replace("_", " ")}',
            "event": f"APPLY_{maintenance_fee_details.fee_type.upper()}",
        },
    )


def get_monthly_mean_balance(
    denomination: str,
    effective_date: datetime,
    creation_date: datetime,
    balances: BalanceTimeseries,
    addresses: List[str],
) -> Decimal:
    """
    Determine the average combined balance for the preceding month. The sampling period is from one
    month before, until the effective_date, exclusive (i.e. not including the effective_date day),
    if the sampling time is before the account was opened then skip that day. Multiple addresses
    can be specified for the calculation.

    :param vault: Vault object
    :param denomination: Account denomination
    :param effective_date: datetime, date and time of hook being run
    :param creation_date: utc account creation date
    :param balances: current balances of account, sampling time is before the account was opened
    :param addresses: list(str), list of addresses to sample and combine the balance for
    :return: mean combined balance at sampling time for previous month
    """
    creation_date = creation_date or effective_date
    period_start = effective_date - timedelta(months=1)
    if period_start < creation_date:
        period_start = creation_date
    # we should always sample at midnight
    period_start.replace(hour=0, minute=0, second=0)
    num_days = (effective_date - period_start).days

    if num_days == 0:
        return None

    total = sum(
        sum(
            balances.at(timestamp=period_start + timedelta(days=i))[
                (address, DEFAULT_ASSET, denomination, Phase.COMMITTED)
            ].net
            for address in addresses
        )
        for i in range(num_days)
    )
    return total / num_days


def get_previous_month_transaction_values_of_type(
    effective_date: datetime,
    denomination: str,
    client_transactions: Dict[Tuple[str, str], ClientTransaction],
    creation_date: datetime,
    types_included: List[str] = None,
    types_excluded: List[str] = None,
) -> List[Decimal]:
    """
    Retrieve all transactions for a given type among all given client_transactions in a monthly
    window. Monthly window is the last month, starting from effective date.

    :param effective_date: datetime
    :param denomination: the denomination the posting instructions will be in
    :param client_transactions: a map of (client_id, client_transaction_id) to a ClientTransaction
    :param creation_date: utc account creation date
    :param types_included: a list of tags that can be found inside a client transaction id, which
        can be used to filter in the transactions of the previous month
    :param types_excluded: a list of tags that can be found inside a client transaction id, which
        can be used to filter out the transactions of the previous month
    :return: list of transaction values for monthly window
    """
    creation_date = creation_date or effective_date

    period_start = effective_date - timedelta(months=1)
    if period_start < creation_date:
        period_start = creation_date

    trans_values_list = [
        client_txn.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].settled
        for (_, client_txn_id), client_txn in client_transactions.items()
        if (
            (
                (types_included and any(incl_type in client_txn_id for incl_type in types_included))
                or (
                    types_excluded
                    and all(excl_type not in client_txn_id for excl_type in types_excluded)
                )
            )
            and client_txn.start_time >= period_start
            and client_txn.effects()[(DEFAULT_ADDRESS, DEFAULT_ASSET, denomination)].settled > 0
        )
    ]

    return trans_values_list
