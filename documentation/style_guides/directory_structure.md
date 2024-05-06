_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Directory Structure

## Product Directory Structure

Our convention is to have:

- one folder per resource type (e.g. account schedule tags, contracts, flags, supervisors, workflows)
- a single test directory (see section below for test specifics)
- other assets at the highest level common to the source files they cover

For example:

```plaintext
|_ product_name/
    |_ useful_asset.py (this is applicable to one or more of the directories below)
    |_ account_schedule_tags/
    |_ contracts/
        |_ useful_asset.py (this is useful within contracts only)
    |_ flag_definitions/
    |_ supervisors/
    |_ workflows/
```

## Test Directory Structure

This applies to all our assets that need testing (product library, SDK etc).
Our convention is to have:

- test files in a `test/` folder (not `tests`)
- separate test folders by test level (e.g. `test/unit` and `test/e2e`). This is optional if there is only one test level
- other assets at the highest level common to the test files they relate to (e.g. test parameter values, dimensions). Be careful not to redefine non-test information here. Parameter names, addresses and other constants should be imported through the tested resource. For example, if a contract is being tested, all parameters should always be imported via the contract, even if they are defined in a feature. This ensures we only import parameters relevant to the tested resource, or are warned if this isn't the case (e.g. `template.feature.PARAM_EXAMPLE` will be flagged before runtime if the parameter is removed fom the feature, or the feature is removed from the template, whereas `feature.PARAM_EXAMPLE` will only be flagged before runtime if the parameter is removed from the feature).

For example:

```plaintext
- dir_a/
    |_ some_constants.py (applicable to source and tests)
    |_ source.py
    |_ test/
        |_ some_constants.py (applicable to unit and e2e)
        |_ unit/test_source.py
        |_ e2e/test_source.py
- dir_b/
    |_ source_2.py
    |_ test/
        |_ test_source_2.py (these tests cover source_2 only, and there is only one test level)
- dir_c/
    |_ source_dir_1/
        |_ source_1_a.py
    |_ source_dir_2/
        |_ source_2_a.py
    |_ test
        |_ test_source.py (these tests cover a combination of source_1_a and source_2_a)
```
