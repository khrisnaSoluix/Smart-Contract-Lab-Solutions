# Cooling-Off period

## Scope

The cooling-off period allows a customer to cancel and fully close their newly opened deposit account without any penalties applied.

## Requirements

[CBF: Cooling-Off Period](https://pennyworth.atlassian.net/browse/CPP-2084)

## Assumptions

- The cooling-off period cut off point will be considered to be the end-of-day of the last day of the cooling-off period. There is no functionality for configuring a different time except end-of-day.

## Proposed Implementation

### Contract Parameters

- `cooling_off_period`: Template parameter, `NumberShape` - The number of days when a user can withdraw money without penalties
- `cooling_off_period_end_date`: Derived parameter, `DateShape` - The date in which the cooling-off period ends

### Technical Logic

- A function that calculates the `cooling_off_period_end_date` by retrieving the account creation date, adding the value of the `cooling_off_period` parameter and setting the time to end-of-day on this date.
- A function that checks whether we are inside the cooling-off period by comparing `effective_datetime` with `cooling_off_period_end_date`.
