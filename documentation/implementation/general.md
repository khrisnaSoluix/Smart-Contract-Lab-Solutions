_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

This file covers general implementation guidance that applies to all/multiple areas of contracts and doesn't fit in other specific sections.

# General

## Do not use datetime.now()/datetime.utcnow()

Although these methods are available in the Contract sandbox, we recommend avoiding them.

### Why

We are often tempted to use these methods inside contracts to generate ‘random’ ids. There are several reasons why this is a bad idea

* It makes testing difficult - SCT means patching is not as obvious as using a third party library like freezegun in a normal unittest
* Simulator behaviour with `utc.now()` is not what you expect (it returns `actual utc.now()`, not the simulated time `utc.now()`)
* It is not foolproof as in theory it can still return the same value in separate executions that happen at the same time
* It can bypass idempotency mechanisms and in general means that hook executions are not reproducible (i.e. republishing a schedule job could result in a different outcome)

### How

flake8_Contracts violation `CTR001` will flag uses of `datetime.now()` and `datetime.utcnow()`. See `documentation/style_guides/python.md` for more details on flake8_Contracts.

## List-type metadata fields should be extended using the unpacking operator (*)

### Why

For developer readability, we want to keep modification of the metadata lists in one place. We can utilise the unpacking operator to extend the event_types list in one line:

```python
event_types = [
    *feature_1.get_event_types(product_name="PRODUCT_NAME"),
    *feature_2.get_event_types(product_name="PRODUCT_NAME"),
]
```

rather than using `+`, `.append()`, `.extend()` or any other method of extending the list.

The list-type metadata fields are: `global_parameters`, `parameters`, `supported_denominations`, `event_types`, `event_types_groups`, `contract_module_imports`, `data_fetchers`.

### How

flake8_Contracts violation `CTR002` will flag when any of the list-type metadata fields are extended outside of their assignment, for example, when `+`, `.append()` or `.extend()` is used. See `documentation/style_guides/python.md` for more details on flake8_Contracts.
