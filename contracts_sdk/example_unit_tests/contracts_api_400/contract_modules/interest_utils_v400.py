from calendar import monthrange
from dateutil.relativedelta import relativedelta


api = "4.0.0"


def get_selected_interest_payday(key_date_timeseries, effective_datetime=None):
    """
    Returns the interest pay day the customer has chosen if the customer has selected a key date,
    otherwise returns None
    """
    if effective_datetime:
        key_date = key_date_timeseries.at(at_datetime=effective_datetime)
    else:
        key_date = key_date_timeseries.latest()
    if key_date.is_set():
        return key_date.value


def get_interest_payday(selected_day, effective_date, has_paid_interest_this_month=False):
    """
    Get next payday value - based on the effective_date it will be next or this month.
    If there is no such day next month as the selected_day,
    the payday will be last day of the month.
    """
    if selected_day <= effective_date.day or has_paid_interest_this_month:
        month_to_be_paid_in = effective_date.replace(day=1) + relativedelta(months=1)
    else:
        month_to_be_paid_in = effective_date.replace(day=1)

    return str(
        min(
            selected_day,
            monthrange(month_to_be_paid_in.year, month_to_be_paid_in.month)[1],
        )
    )
