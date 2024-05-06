_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

This file covers guidance specific to the way we implement templates.

# Contract Templates

## Template Structure

We structure our templates in the following way:

- imports
- constants
- contract metadata fields
  - event_types
  - fetchers
  - parameters
- hook implementations
- helper functions

### Template Constants

Templates should aim to re-use common definitions. Product-specific constants can also be added, taking care to avoid conflicts.

#### Why

It is crucial to keep this structure to avoid deviating duplicate definitions, or namespacing conflicts. As the renderer currently allows these conflicts, which are technically valid Python, they can cause tricky bugs that are hard to debug:

- Consider `addresses.py` and `features/v4/common/addresses.py` that both define a list constant named `ACCRUAL_ADDRESSES` with different list items. Balance sums over these lists can differ and cause subtle changes to calculations.
- Upon rendering, the final contract will have two definition of `addresses_ACCRUAL_ADDRESSES`. Depending on the ordering of these definitions, the expected or definition may or may not be used.
- Although we plan to make the renderer stricter with these namespacing errors, redefining addresses unnecessarily at best adds unnecessary extra code, and at worst causes confusion.

#### How

Using mortgage and address constants as an example, we adopt the following import structure in the template:

```plaintext
<product>
    |__<product>_addresses.py <- specific to the product and do not exist anywhere else. Defined in the same folder as the template. It is important to have the <product> prefix as supervisor-based implementations may import from multiple products.
    |__ features/v4/common/common_addresses.py <- potentially applicable to all products and should not be redefined by any product.
    |__ features/v4/product_group/<product_group>_addresses.py <- potentially applicable to all products within a product group (e.g. lending) and should not be redefined by any product in that group.
```

Within templates, the python namespacing makes it clear where the constants come from (`<product>_addresses.ADDRESS_X` vs `common_addresses.ADDRESS_Y`).

Within rendered contracts, the renderer namespacing preserves this clarity (`<product>_addresses_ADDRESS_X` vs `common_addresses_ADDRESS_Y`).

Within tests, the addresses are all still easily accessible via the template's module (e.g. `<product>.<product>_addresses.ADDRESS_X` or `<product>.lending_addresses.ADDRESS_Z`).
