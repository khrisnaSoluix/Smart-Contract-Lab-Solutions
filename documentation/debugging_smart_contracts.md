_© Thought Machine Group Limited 2021_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Debugging Smart Contracts

## General information

If a contract is not behaving as expected, aim to recreate the problem in a unit test as this provides the fastest and easiest method of investigation.

## Output from test files

Logging (or print) statements can be used in all types of test to output information. Some test runners may only show the output if a test fails unless requested e.g. `plz test --show_all_output` for the open-source build system [Please](https://www.please.build).

Example of commands to output logging from a test file:

```python
import logging
log = logging.getLogger(__name__)

log.info(f"Outputting value {value}")
```

## Inspecting contract behaviour

To see what happens when a contract executes, different approaches are available depending on the level of the test.

## Unit tests

When running unit tests the contract is executed by the standard Python interpreter so generic _Python tooling_ may be used, such as IDE debug features.

_Logging_ (or printing) information is also possible from within the contract (remove once the debugging is finished).

The _calls made_ to the Vault mock can be seen by outputting `mock_vault.mock_calls`.

## Simulated and live scenarios

Most of these approaches apply to both simulation and end-to-end tests and, if necessary, for debugging behaviour in a real environment:

### Inspecting data with Account Notes (Contracts API 3.x only)

_Account notes_ can be used to output information from scheduled events and most hooks.

```python
vault.add_account_note(
    body=f"calculation {result} info here",
    note_type=NoteType.RAW_TEXT,
    is_visible_to_customer=True,
    date=effective_date
)
```

In an e2e test the data is visible in the Operations Dashboard "messages" section in the account created by the test. For a simulation test the information is available in the object returned from the simulation:

```python
from inception_sdk.test_framework.contracts.simulation.utils import get_account_notes
...
print(get_account_notes(res, "Account Name"))
```

### Inspecting data with Account Notifications

_Account Notifications_ can be used to output information from scheduled events and most hooks.

```python
AccountNotificationDirective(
    notification_type="DUMMY_NOTIFICATION",
    notification_details={
        "useful_information": "for debugging",
    },
)
```

In an e2e test the data is visible on the Contract events topic `vault.core_api.v1.contracts.contract_notification.events`

### Putting data into a debug Posting

Adding a dummy _posting_ to a posting batch with debug information is a similar way of seeing information, by inserting data into the `instruction_details`. This can then be viewed in the simulation response object or the account view in the Operations Dashboard.

In Contracts API 3.x:

```python
posting_ins.extend(
    vault.make_internal_transfer_instructions(
        amount=Decimal(1),
        denomination=denomination,
        from_account_id=vault.account_id,
        from_account_address=DEFAULT_ADDRESS,
        to_account_id=vault.account_id,
        to_account_address="DEBUG",
        asset=DEFAULT_ASSET,
        override_all_restrictions=True,
        client_transaction_id=f"DEBUG_ACCRUED_OVERDRAFT_FEE"
                                f"_{vault.get_hook_execution_id()}"
                                f"_{denomination}_CUSTOMER",
        instruction_details={
            "description": f"Balances {str(balances.keys())}\ndenom {denomination}\nnet {balances[('OVERDRAFT_FEE', DEFAULT_ASSET, denomination, Phase.COMMITTED)].net}\n{str(effective_date)}",
            "event": "APPLY_ACCRUED_OVERDRAFT_FEE"
        }
    )
)
```

In Contracts API 4.x:

```python
CustomInstruction(
    postings=[
        Posting(
            credit=False,
            amount=Decimal(1),
            denomination="DBG",
            account_id=account_id,
            account_address="DEBUG_ADDRESS",
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
        Posting(
            credit=True,
            amount=Decimal(1),
            denomination="DBG",
            account_id=deposit_account_id,
            account_address="DEBUG_ADDRESS",
            asset=DEFAULT_ASSET,
            phase=Phase.COMMITTED,
        ),
    ],
    override_all_restrictions=True,
    instruction_details={
        "debug_information": "here"
    },
)
```

### Derived parameters

A temporary _derived parameter_ can be used to output information, for example to show the working steps of a calculation.

In Contracts API 3.x:

```python
parameters = [
    # ...
    Parameter(
        name="debug_information",
        shape=StringShape,
        level=Level.INSTANCE,
        derived=True,
        description="Temporary information",
        display_name="Temporary information"
    ),
    # ...
]


@requires(parameters=True, balances="latest live")
def derived_parameters(effective_date):
  balances = vault.get_balance_timeseries().latest()

  return {
      "debug_information": "Debug information...."
  }
```

In Contracts API 4.x:

```python
parameters = [
    # ...
    Parameter(
        name="debug_information",
        shape=StringShape(min_value=0),
        level=ParameterLevel.INSTANCE,
        derived=True,
        description="Temporary information",
        display_name="Temporary information"
    )
]

@requires(parameters=True)
def derived_parameter_hook(
    vault, hook_arguments: DerivedParameterHookArguments
) -> DerivedParameterHookResult:

    return {
        "debug_information": "Debug information...."
    }

```

### Debugging the pre-posting hook

The pre-posting hook is a special case. The Vault API is deliberately limited for this hook to maximise performance on the "hot-path", and the above techniques are not available. One method of investigating the pre-posting hook is to raise a "Rejection" exception with information in it, which is then viewable either in the simulation response object or, for a live environment, in the Kafka response topic or contract-executor log.
.

In Contracts API 3.x:

```python

def pre_posting_code(postings, effective_date):
    # ...
    # See posting instruction rejection details from Kafka with something like:
    # kafkacat -b kafka.kafka-v2-<environment-url> -C -t vault.core.postings.async_creation_api.responses
    raise Rejected(
        f"Debug information here",
        reason_code=RejectedReason.INSUFFICIENT_FUNDS,
    )
```

In Contracts API 4.x:

```python
def pre_posting_hook(
    vault: SmartContractVault, hook_arguments: PrePostingHookArguments
) -> Optional[PrePostingHookResult]:
    return PrePostingHookResult(
        rejection=Rejection(
            message="Debug information here",
            reason_code=RejectionReason.CLIENT_CUSTOM_REASON,
        )
    )
```
