display_name = "Instant Saver"
api = "3.4.0"
version = "1.0.0"

parameters = [
    Parameter(
        name="key_date",
        level=Level.INSTANCE,
        description="Do you want to choose the day you are paid interest?",
        display_name="Elected day of month to pay interest on",
        shape=OptionalShape(
            NumberShape(
                min_value=1,
                max_value=31,
                step=1,
            )
        ),
        update_permission=UpdatePermission.USER_EDITABLE,
        default_value=OptionalValue(Decimal(28)),
    ),
]


@requires(parameters=True)
def execution_schedules():
    start_date = vault.get_account_creation_date()
    selected_day = _get_selected_interest_payday(vault, effective_date=start_date)
    payday = _get_interest_payday(selected_day, start_date)
    return (
        ("APPLY_ACCRUED_INTEREST", {"day": payday, "hour": "0", "minute": "1"}),
        ("ACCRUE_INTEREST", {"hour": "0"}),
    )


def pre_parameter_change_code(parameters, effective_date):
    # Set the default value to the open date of the account
    if "key_date" in parameters:
        parameters["key_date"].default_value = OptionalValue(
            Decimal(vault.get_account_creation_date().day)
        )
    return parameters


@requires(parameters=True, last_execution_time=["APPLY_ACCRUED_INTEREST"])
def post_parameter_change_code(old_parameter_values, updated_parameter_values, effective_date):
    if "key_date" not in updated_parameter_values:
        return

    vault.amend_schedule(event_type="APPLY_ACCRUED_INTEREST", new_schedule=None)


def _get_selected_interest_payday(vault, effective_date=None):
    """
    Get the interest pay day the customer has chosen or the day the account was opened if the
    customer has not selected a key date.
    """
    if effective_date:
        key_date = vault.get_parameter_timeseries(name="key_date").at(timestamp=effective_date)
    else:
        key_date = vault.get_parameter_timeseries(name="key_date").latest()
    return key_date.value if key_date.is_set() else vault.get_account_creation_date().day


def _get_interest_payday(selected_day, effective_date, has_paid_interest_this_month=False):
    if selected_day <= effective_date.day or has_paid_interest_this_month:
        month_to_be_paid_in = effective_date.replace(day=1) + timedelta(months=1)
    else:
        month_to_be_paid_in = effective_date.replace(day=1)

    return str(
        min(
            selected_day,
            calendar.monthrange(month_to_be_paid_in.year, month_to_be_paid_in.month)[1],
        )
    )


# flake8: noqa: F821
