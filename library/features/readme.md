_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Feature Library Folder Structure

## Context

Our current approach to Product Composition sits at a 'Product-Group' level. This means we primarily aim to share features between products that are part of the same product group.
From a functional perspective, the library products fall into two main groups, and the sub-groups for lending:
    1. Deposits (T-Side: Liability)
    2. Lending (T-Side: Assets)
       1. Revolving
       2. Non-Revolving
The functional groups also map to our technical architectures, so it makes sense to use a similar hierarchy for our features. We also recognise there are some common utilities that are likely to be used across all product groups, but these are unlikely to be fully fledged product features.
Finally, there are exceptions for Islamic banking/Shariah, which does not necessarily align to the same definitions as Western banking.

Whilst v3 and v4 contracts language duality exists in the library we need to make a distinction between features written in the different api versions. Therefore, the following approach is adopted:

1. Existing features have been moved to a v3 subfolder within library/features
2. Newly written features in v4 will exist inside the v4 subfolder
3. Any logic that can be shared between the v3 and v4 version of the feature will exist in a common folder, with the file appropriately named `<feature_name>_common.py` The `_common` suffix is required for renderer namespacing. `<feature_name>_common.py` should only ever be imported into the v3 or v4 feature itself and never directly into a contract template.

## Desired Structure

Within `library/features` we will therefore stick to:

```plaintext
|__common/
|__ v3/
|   |__deposits/
|   |__ lending/
|   |__shariah/
|__ v4/
|   |__deposits/
|   |__ lending/
|   |__ shariah/
```

Within `shariah` we can re-use a similar structure as `library/features` but for the relevant Shariah groups (`deposits` and `financing`).

Each folder should only contain features that are applicable to all products fitting that description. For example:

- `library/features/v3/common` should be applicable to all v3 products (i.e. if a feature assumes a given TSide it should not go here)
- `library/features/v3/deposits` should be applicable to all v3 deposit products
- `library/features/v4/common` should be applicable to all v4 products (i.e. if a feature assumes a given TSide it should not go here)
- `library/features/v4/deposits` should be applicable to all v4 deposit products

There are some special cases:

- If the library does not contain features to justify a distinction, this can be omitted until necessary. For example, we may not split `lending` into `lending/revolving` and `lending/non_revolving` until we need to
- If features are written for a specific product rather than a product group, we will leave the features in the product folder (e.g. we will accept `library/<product>/features/<feature_file>`)
- In the case of `shariah` we will accept re-using features from `library/features/v3/deposits` if suitable (i.e. interest-related features should not be used, but transaction-limit features could be)

## Design decisions

1. NamedTuples are used as a make-shift interface for features which need to be implemented else where. The NamedTuple object should be instantiated and assigned to a variable called `feature`.

# Parameter Naming Conventions

When importing a feature into a financial product, the product may not need all of the parameters defined by the feature; to account for this each feature will include an `all_parameters` list that comprises a subset of parameter lists grouped by their use. The convention is as follows:

- `all_parameters` = `[*<group_1>_parameters, *<group_2>_parameters, *<group_3>_parameters>]`
For example, the interest accrual feature has the following parameter lists:
- `all_parameters` = `[*schedule_parameters, *account_parameters]`
