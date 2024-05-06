# Financial Product Encapsulation

## Assumptions

N/A

## Encapsulation

Contracts should follow the general encapsulation design pattern. Any implementation details, such as computations that contracts perform, or other internal mechanics required to achieve a feature, should be abstracted away from relevant services to avoid coupling. Contract designs should also aim to avoid duplication of logic across contract and services. Together, these help simplify deployments and reduce cost of change.

There are general mechanisms available in contracts to help achieve this, as well as some design/implementation patterns to follow.

### Derived Parameters

Derived parameters help expose information to callers without tightly coupling them to mechanics. A classic example is using a derived parameter for a loan's EMI. This way the service does not need to concern itself with the financial logic and data to perform the calculation.

### Notifications

Notifications (see `documentation/design_decisions/generation_notifications.md`) help the contract issue generic triggers to external systems. The notification content effectively forms an interface that decouples the external systems from the internal contract mechanics.

### Custom Balance definitions

Features that use custom balance definitions should include logic to tidy up behind them to avoid leaving non-zero balances as part of account closure. See the details about `close_code` (Contracts API 3.x) / `deactivation_hook` (Contracts API 4.x) in the `documentation/implementation/hooks.md` for more details on this.

In general, custom balances themselves need to be considered carefully:

  1. They can be seen as undesirable because they promote coupling to an implementation detail. For example,  services should not start relying on balance definitions without the contract writer knowing, or they may be affected by implementation changes.
  2. They can act as a way to decouple contract and services, because Vault does not provide a mechanism to stream aggregated balances. Storing them in a custom balance definition addresses this gap.
It is therefore sensible for the contract writer to define which custom balance definitions are considered to be part of the interface that services can rely on and won't be affected by non-backwards-compatible implementation changes.
