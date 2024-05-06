# Generating Notifications

## Assumptions

There are notification use cases that are not driven by Vault features/data (e.g. promotional campaigns), or only partially driven (e.g. a statement will combine Vault data and other information from the client side). We therefore assume that the notification engine itself is a client service. Smart contracts will need to provide the engine with the data and/or trigger to generate and transmit a notification through the relevant mediums (e.g. mobile app, email, text message)

## Notification Types

We can broadly categorise the notifications use cases from a smart contract perspective as follows.

### Implicit Notifications

Implicit notifications are directly tied to and solely reliant on the mutation of first class Vault resources (e.g. a notification for a fee being charged based on a posting being created):

### Explicit Notifications

Explicit notifications aren’t directly tied to or require significant enrichment beyond the related first class Vault resources (e.g. providing statement related data). In some scenarios it may be possible to use a combination of first class resources, but the linkage logic can be complex or even unachievable (e.g. relating schedule, balance and posting changes for a credit card statement).

## Design

### Implicit Notifications Design

As the mutations themselves will result in Kafka events emitted via the relevant Streaming API (e.g. Core Streaming API), implicit notifications generally require no further effort from a smart contract perspective. However, there may be metadata considerations to allow the Streaming API events to be processed (e.g. add a `fee_type` key-value pair to a posting instruction’s instruction details). This is trivial so we will ignore this for now.

There are some resources that lack platform support for streaming events (e.g. schedules), so these fall into the next category for the time being. Per-contract requirements will need to be considered to determine if explicit notifications are required due to gaps in platform features (e.g. a change to a schedule date that needs notifying)

### Explicit Notifications Design

If we do not have any built-in first class resources, or the linkage between them is too complex for some scenarios, the smart contract will need to generate explicit notifications. The Contract API's Contract Notification feature is designed specifically for this purpose.

> **_NOTE:_** Prior to the Contract Notification feature being available the recommended approach was to use a Dummy Workflow. This practice is now deprecated and no longer present in the Product Library.
