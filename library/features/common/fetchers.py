# contracts api
from contracts_api import (
    BalancesObservationFetcher,
    DefinedDateTime,
    Override,
    PostingsIntervalFetcher,
    RelativeDateTime,
    Shift,
    BalancesFilter
)

# Balance Observation Fetchers
EOD_FETCHER_ID = "EOD_FETCHER"
EOD_FETCHER = BalancesObservationFetcher(
    fetcher_id=EOD_FETCHER_ID,
    at=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME, find=Override(hour=0, minute=0, second=0)
    ),
)

NRS_ACCRUAL = "NRS_ACCRUAL"
NRS_ACCRUAL_LIVE_BOF_ID = "NRS_ACCRUAL_LIVE_FETCHER"
NRS_ACCRUAL_LIVE_BOF = BalancesObservationFetcher(
    fetcher_id=NRS_ACCRUAL_LIVE_BOF_ID,
    at=DefinedDateTime.LIVE,
    filter=BalancesFilter(addresses=[NRS_ACCRUAL]),
)

EFFECTIVE_OBSERVATION_FETCHER_ID = "EFFECTIVE_FETCHER"
EFFECTIVE_OBSERVATION_FETCHER = BalancesObservationFetcher(
    fetcher_id=EFFECTIVE_OBSERVATION_FETCHER_ID, at=DefinedDateTime.EFFECTIVE_DATETIME
)

LIVE_BALANCES_BOF_ID = "live_balances_bof"
LIVE_BALANCES_BOF = BalancesObservationFetcher(
    fetcher_id=LIVE_BALANCES_BOF_ID,
    at=DefinedDateTime.LIVE,
)

# Previous EOD Balance Observation Fetchers
PREVIOUS_EOD_1_FETCHER_ID = "PREVIOUS_EOD_1_FETCHER_ID"
PREVIOUS_EOD_1_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_1_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-1),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_2_FETCHER_ID = "PREVIOUS_EOD_2_FETCHER_ID"
PREVIOUS_EOD_2_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_2_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-2),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_3_FETCHER_ID = "PREVIOUS_EOD_3_FETCHER_ID"
PREVIOUS_EOD_3_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_3_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-3),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_4_FETCHER_ID = "PREVIOUS_EOD_4_FETCHER_ID"
PREVIOUS_EOD_4_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_4_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-4),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_5_FETCHER_ID = "PREVIOUS_EOD_5_FETCHER_ID"
PREVIOUS_EOD_5_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_5_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-5),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_6_FETCHER_ID = "PREVIOUS_EOD_6_FETCHER_ID"
PREVIOUS_EOD_6_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_6_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-6),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_7_FETCHER_ID = "PREVIOUS_EOD_7_FETCHER_ID"
PREVIOUS_EOD_7_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_7_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-7),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_8_FETCHER_ID = "PREVIOUS_EOD_8_FETCHER_ID"
PREVIOUS_EOD_8_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_8_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-8),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_9_FETCHER_ID = "PREVIOUS_EOD_9_FETCHER_ID"
PREVIOUS_EOD_9_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_9_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-9),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_10_FETCHER_ID = "PREVIOUS_EOD_10_FETCHER_ID"
PREVIOUS_EOD_10_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_10_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-10),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_11_FETCHER_ID = "PREVIOUS_EOD_11_FETCHER_ID"
PREVIOUS_EOD_11_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_11_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-11),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_12_FETCHER_ID = "PREVIOUS_EOD_12_FETCHER_ID"
PREVIOUS_EOD_12_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_12_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-12),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_13_FETCHER_ID = "PREVIOUS_EOD_13_FETCHER_ID"
PREVIOUS_EOD_13_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_13_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-13),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_14_FETCHER_ID = "PREVIOUS_EOD_14_FETCHER_ID"
PREVIOUS_EOD_14_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_14_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-14),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_15_FETCHER_ID = "PREVIOUS_EOD_15_FETCHER_ID"
PREVIOUS_EOD_15_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_15_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-15),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_16_FETCHER_ID = "PREVIOUS_EOD_16_FETCHER_ID"
PREVIOUS_EOD_16_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_16_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-16),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_17_FETCHER_ID = "PREVIOUS_EOD_17_FETCHER_ID"
PREVIOUS_EOD_17_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_17_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-17),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_18_FETCHER_ID = "PREVIOUS_EOD_18_FETCHER_ID"
PREVIOUS_EOD_18_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_18_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-18),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_19_FETCHER_ID = "PREVIOUS_EOD_19_FETCHER_ID"
PREVIOUS_EOD_19_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_19_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-19),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_20_FETCHER_ID = "PREVIOUS_EOD_20_FETCHER_ID"
PREVIOUS_EOD_20_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_20_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-20),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_21_FETCHER_ID = "PREVIOUS_EOD_21_FETCHER_ID"
PREVIOUS_EOD_21_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_21_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-21),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_22_FETCHER_ID = "PREVIOUS_EOD_22_FETCHER_ID"
PREVIOUS_EOD_22_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_22_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-22),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_23_FETCHER_ID = "PREVIOUS_EOD_23_FETCHER_ID"
PREVIOUS_EOD_23_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_23_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-23),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_24_FETCHER_ID = "PREVIOUS_EOD_24_FETCHER_ID"
PREVIOUS_EOD_24_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_24_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-24),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_25_FETCHER_ID = "PREVIOUS_EOD_25_FETCHER_ID"
PREVIOUS_EOD_25_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_25_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-25),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_26_FETCHER_ID = "PREVIOUS_EOD_26_FETCHER_ID"
PREVIOUS_EOD_26_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_26_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-26),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_27_FETCHER_ID = "PREVIOUS_EOD_27_FETCHER_ID"
PREVIOUS_EOD_27_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_27_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-27),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_28_FETCHER_ID = "PREVIOUS_EOD_28_FETCHER_ID"
PREVIOUS_EOD_28_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_28_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-28),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_29_FETCHER_ID = "PREVIOUS_EOD_29_FETCHER_ID"
PREVIOUS_EOD_29_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_29_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-29),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_30_FETCHER_ID = "PREVIOUS_EOD_30_FETCHER_ID"
PREVIOUS_EOD_30_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_30_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-30),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_31_FETCHER_ID = "PREVIOUS_EOD_31_FETCHER_ID"
PREVIOUS_EOD_31_FETCHER = BalancesObservationFetcher(
    fetcher_id=PREVIOUS_EOD_31_FETCHER_ID,
    at=RelativeDateTime(
        shift=Shift(days=-31),
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        find=Override(hour=0, minute=0, second=0),
    ),
)

PREVIOUS_EOD_OBSERVATION_FETCHERS = [
    PREVIOUS_EOD_1_FETCHER,
    PREVIOUS_EOD_2_FETCHER,
    PREVIOUS_EOD_3_FETCHER,
    PREVIOUS_EOD_4_FETCHER,
    PREVIOUS_EOD_5_FETCHER,
    PREVIOUS_EOD_6_FETCHER,
    PREVIOUS_EOD_7_FETCHER,
    PREVIOUS_EOD_8_FETCHER,
    PREVIOUS_EOD_9_FETCHER,
    PREVIOUS_EOD_10_FETCHER,
    PREVIOUS_EOD_11_FETCHER,
    PREVIOUS_EOD_12_FETCHER,
    PREVIOUS_EOD_13_FETCHER,
    PREVIOUS_EOD_14_FETCHER,
    PREVIOUS_EOD_15_FETCHER,
    PREVIOUS_EOD_16_FETCHER,
    PREVIOUS_EOD_17_FETCHER,
    PREVIOUS_EOD_18_FETCHER,
    PREVIOUS_EOD_19_FETCHER,
    PREVIOUS_EOD_20_FETCHER,
    PREVIOUS_EOD_21_FETCHER,
    PREVIOUS_EOD_22_FETCHER,
    PREVIOUS_EOD_23_FETCHER,
    PREVIOUS_EOD_24_FETCHER,
    PREVIOUS_EOD_25_FETCHER,
    PREVIOUS_EOD_26_FETCHER,
    PREVIOUS_EOD_27_FETCHER,
    PREVIOUS_EOD_28_FETCHER,
    PREVIOUS_EOD_29_FETCHER,
    PREVIOUS_EOD_30_FETCHER,
    PREVIOUS_EOD_31_FETCHER,
]
PREVIOUS_EOD_OBSERVATION_FETCHER_IDS = [
    PREVIOUS_EOD_1_FETCHER_ID,
    PREVIOUS_EOD_2_FETCHER_ID,
    PREVIOUS_EOD_3_FETCHER_ID,
    PREVIOUS_EOD_4_FETCHER_ID,
    PREVIOUS_EOD_5_FETCHER_ID,
    PREVIOUS_EOD_6_FETCHER_ID,
    PREVIOUS_EOD_7_FETCHER_ID,
    PREVIOUS_EOD_8_FETCHER_ID,
    PREVIOUS_EOD_9_FETCHER_ID,
    PREVIOUS_EOD_10_FETCHER_ID,
    PREVIOUS_EOD_11_FETCHER_ID,
    PREVIOUS_EOD_12_FETCHER_ID,
    PREVIOUS_EOD_13_FETCHER_ID,
    PREVIOUS_EOD_14_FETCHER_ID,
    PREVIOUS_EOD_15_FETCHER_ID,
    PREVIOUS_EOD_16_FETCHER_ID,
    PREVIOUS_EOD_17_FETCHER_ID,
    PREVIOUS_EOD_18_FETCHER_ID,
    PREVIOUS_EOD_19_FETCHER_ID,
    PREVIOUS_EOD_20_FETCHER_ID,
    PREVIOUS_EOD_21_FETCHER_ID,
    PREVIOUS_EOD_22_FETCHER_ID,
    PREVIOUS_EOD_23_FETCHER_ID,
    PREVIOUS_EOD_24_FETCHER_ID,
    PREVIOUS_EOD_25_FETCHER_ID,
    PREVIOUS_EOD_26_FETCHER_ID,
    PREVIOUS_EOD_27_FETCHER_ID,
    PREVIOUS_EOD_28_FETCHER_ID,
    PREVIOUS_EOD_29_FETCHER_ID,
    PREVIOUS_EOD_30_FETCHER_ID,
    PREVIOUS_EOD_31_FETCHER_ID,
]

# Postings Interval Fetchers

# Retrieves all the postings that happened during the effective date
# from: <effective_date>T00:00:00 to: <effective_date>Thh:mm:ss
# Note: This fetcher has been defined with the specific end delimiter of EFFECTIVE_DATETIME to
# ensure that when used in the post posting hook the only postings instructions retrieved are the
# ones committed before the proposed posting instructions are processed. This will prevent other
# concurrent operations from being incorrectly retrieved, since the END delimiter defaults to LIVE
EFFECTIVE_DATE_POSTINGS_FETCHER_ID = "EFFECTIVE_DATE_POSTINGS_FETCHER"
EFFECTIVE_DATE_POSTINGS_FETCHER = PostingsIntervalFetcher(
    fetcher_id=EFFECTIVE_DATE_POSTINGS_FETCHER_ID,
    start=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME, find=Override(hour=0, minute=0, second=0)
    ),
    end=DefinedDateTime.EFFECTIVE_DATETIME,
)

MONTHLY_POSTINGS_FETCHER_ID = "MONTHLY_POSTINGS_FETCHER"
MONTHLY_POSTINGS_FETCHER = PostingsIntervalFetcher(
    fetcher_id=MONTHLY_POSTINGS_FETCHER_ID,
    start=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME,
        shift=Shift(months=-1),
        find=Override(hour=0, minute=0, second=0),
    ),
    end=DefinedDateTime.EFFECTIVE_DATETIME,
)

# Retrieves all the postings that happened from start of month of effective datetime to
# the effective date and time.
# from: <first_day_of_effective_date_month>T00:00:00 to: <effective_date>Thh:mm:ss
# Note: This fetcher has been defined with the specific end delimiter of EFFECTIVE_DATETIME to
# ensure that when used in the post posting hook the only postings instructions retrieved are the
# ones committed before the proposed posting instructions are processed. This will prevent other
# concurrent operations from being incorrectly retrieved.
MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID = "MONTH_TO_EFFECTIVE_POSTINGS_FETCHER"
MONTH_TO_EFFECTIVE_POSTINGS_FETCHER = PostingsIntervalFetcher(
    fetcher_id=MONTH_TO_EFFECTIVE_POSTINGS_FETCHER_ID,
    start=RelativeDateTime(
        origin=DefinedDateTime.EFFECTIVE_DATETIME, find=Override(day=1, hour=0, minute=0, second=0)
    ),
    end=DefinedDateTime.EFFECTIVE_DATETIME,
)
