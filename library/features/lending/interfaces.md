# Interfaces
The debt management module defines a number of interfaces in order to customise the behaviour. This allows the core architecture to be re-usable across many different product variants.

If the specific implementation does not need one or more of the arguments mentioned in the interface, they can be marked as optional (e.g. `elapsed_term_in_months: Optional[int] = None`). The doc string should be updated to include any additional relevant information.

## Interest application

The `get_application_posting_instructions` method returns any posting instructions required to implement behaviours relating to applying interest in the DUE_AMOUNT_CALCULATION schedule. These are typically related to behaviours at accrual. For example:
- Rounding and moving ACCRUED_INTEREST to INTEREST_DUE
- Zeroing out ACCRUED_EXPECTED_INTEREST if overpayments are used

```python
def get_application_posting_instructions(
    vault: Vault,
    effective_date: datetime,
    denomination: str,
    applied_to_address: str = DEFAULT_ADDRESS,
    accrued_at_address: str = interest_accrual.ACCRUED_INTEREST_RECEIVABLE_ADDRESS,
) -> list[PostingInstruction]:
```

## Reamortisation

The `should_trigger_reamortisation` method is used to determine whether reamortisation is required in the DUE_AMOUNT_CALCULATION schedule. For example:
- A change to the loan's interest rate
- A change to the principal that needs to impact the EMI

```python
def should_trigger_reamortisation(
    vault: Vault,
    elapsed_term_in_months: int,
    due_amount_schedule_details: ScheduleDetails,
    **kwargs
) -> bool:
    """
    Determines whether reamortisation is required.
    :param vault: the vault object to use to fetch data (balances, parameters etc)
    :param elapsed_term_in_months: the number of elapsed terms for the loan
    :param due_amount_schedule_details: the details of the due amount schedule
    :param kwargs:
    :return: True if reamortisation is required, False otherwise
    """
    pass
```

## Principal Adjustment
The `get_principal_adjustment_posting_instructions` method returns any posting instructions required to implement behaviours relating to principal amount adjustments in the DUE_AMOUNT_CALCULATION schedule. For example:
- an overpayment directly reduces the remaining principal, which can in turn reduce the interest to pay and increase the principal portion of the EMI. This indirectly reduces the principal further
- interest is capitalised and added to principal

```python
def get_principal_adjustment_posting_instructions(
    vault: Vault,
    denomination: str,
    principal_address: str
) -> list[PostingInstruction]:
```

The `get_principal_adjustment_amount` method returns the sum total of the features' principal adjustment amounts. This does not necessarily match the amounts from `get_principal_adjustment_posting_instructions` postings as there can be multiple ways in which a feature affects principal.

```python
def get_principal_adjustment_amount(
    vault: Vault,
) -> Decimal:
```