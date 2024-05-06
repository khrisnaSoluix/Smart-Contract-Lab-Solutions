# Design Anti-Patterns

We should avoid the following anti-patterns, which are usually introduced at the design stage rather than implementation.

Unless specified otherwise `PostingInstruction` (Contracts API 3.x) is interchangeable with `Union[AuthorisationAdjustment, CustomInstruction, InboundAuthorisation, InboundHardSettlement, OutboundAuthorisation, OutboundHardSettlement, Release, Settlement, Transfer]` for fetched / hook argument data, or `CustomInstruction` for contract-generated data. `PostingInstructionBatch` (Contracts API 3.x) is interchangeable with `PostingInstructionsDirective` (Contracts API 4.x) for contract-generated data.  `PostingInstructionBatch` is replaced by `list[Union[AuthorisationAdjustment, CustomInstruction, InboundAuthorisation, InboundHardSettlement, OutboundAuthorisation, OutboundHardSettlement, Release, Settlement, Transfer]]` in Contracts API 4.x for fetched / hook argument data, which won't have equivalents for class methods or attributes.

## Unbounded Balance Definition Count

As a general rule, contracts should be designed to rely on a fixed or at least capped number of custom balance definitions (i.e. those that do not have the `DEFAULT` address). Any design that creates new custom addresses assets, or denominations based on input values that have endless possible values will inevitably create enough custom balance definitions that performance will be affected. Once a contract does have a fixed/capped number of custom balance definitions, the focus should be on minimising the number it needs. This is because the more custom balance definitions there are, the longer fetching will take. This will ultimately affect performance under load.

An easy way to determine if a design is affected is to ask the question "what is the maximum number of balance definition the contract will use?". If the answer is "it depends on [Insert other system name]" or "there is no maximum" then the design should be revisited. There are also some specific decisions that can lead to this type of design, so if a contract does any of the following it is at risk:

- Generating postings to balance definition attributes derived from `PostingInstructionBatch` or `PostingInstruction` attributes that aren't enumerated. For example, using any of the following will mean an ever-growing number of addresses:
  - Datetime attributes, such as `value_timestamp`
  - Unique id fields, such as `client_transaction_id` or `id`
  - Metadata fields like `batch_details` or `instruction_details` can be OK, but only if they have a pre-determined list of accepted values. If upstream systems can send in infinite unique values this will mean an ever-growing number of addresses.
  - Outputs of methods like `datetime.now()`, `datetime.utcnow()` or any variants should be avoided anyway (see documentation/implementation/general.md), but are especially dangerous in the context of balance definitions
  - If multiple attributes are used, be sure to consider the multiplicative impact
- Generating postings to addresses derived from parameter values:
  - Parameter values are similar to contents of metadata fields in this context. A finite list of parameter values can be OK, but not if other systems can update these parameters to contain unlimited variations of values
  - If multiple parameters are involved, be sure to consider the multiplicative impact
- Generating postings to addresses derived from flags:
  - This arguably falls under parameter values, as the flags that a contract cares about are often hardcoded, or parameterised.
  - There are often many flag definitions as they are a) versatile and b) binary indicators. This means it is easy to

Note that it is not a problem to use the above attributes (barring `datetime` methods) to determine when to create postings, or their amounts. The issue only arises when these attributes are used to determine the posting attributes that form part of Balance Definition (address, asset, denomination)

## Multi-Product Contracts

Contracts should generally be designed to implement a specific product. If this product can be broken down into two separate product states (a product might convert from one product to another in response to a trigger), these are usually better off being implemented as separate contracts. One example might be a Home Equity Line of Credit, which would convert from a Line of Credit during the draw period to a Home Loan during the repayment period.

There are a number of considerations behind this guidance and the following points demonstrate the complexities with a single multi-product contract:

- Support and maintenance is made harder due to a higher amount of code potentially affected when the hybrid contract is changed, despite large portions of the code only being temporarily relevant to the account in question. Fixing one part of the product’s lifecycle can undesirably affect the other part.

- Migrations and upgrades are made harder as they need to handle accounts that can be in any of the product states. This would involve creating/recreating/amending the right schedules, balances etc accordingly. An upgrade to fix one product state could end up affecting the other product state undesirably. Migrating a subset of accounts to limit this impact isn't ideal as a) the subset is not fixed and it is easy to accidentally include/exclude accounts, and b) if there are more than two states you often still need to consider multiple states in the upgrade.

- There is a performance impact from previous product states (e.g. old balance definitions). Whilst Optimised Data Fetchers can be configured to only include specific balance addresses, which could exclude balances from previous product states, this cannot be achieved in all hooks on a single product without a code change. For example, the pre-posting hook has a single fetcher configuration, and can't switch from fetching addresses A and B to C and D without a code change. Certain hooks are less prone to this, as each schedule has its own fetcher configuration and we could use different schedules across the product states.

- Re-use. For example, if a hybrid product converts from product A to product B and we have suitable contracts for both of these, we wouldn't be able to re-use them directly. This leads us to creating new contracts, which come with associated costs. This is somewhat mitigated by Product Composition, but we would still lower our level of re-use from product-level to business feature-level and still need to write additional tests for the hybrid cross-over etc.

- Ease of access to data. It may not be obvious when/how to retrieve data for the first state of the hybrid product once it has cutover to another state. For example, external consumers will need to query balances, parameters etc as of a specific datetime, which could be defined by the product or externally, which muddies the water. In contrast, with the two contracts/accounts, the closure of the first account/opening of second account provide an easy reference point.
