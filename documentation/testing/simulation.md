_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Simulation Tests

## Initializing template and instance parameters

We encourage dictionary unpacking and proper indentation when declaring template and instance parameters inside tests.

### Why

This helps improve readability by making it very clear which values belong to the template_params and which values belong to the instance_params while also discouraging interleaving of dictionary initialization code.

### How

1. Define the default parameters globally
2. Soft copy the default parameters when initializing parameters in tests. For example:

    ```python
    template_params = {
        **default_template_params,
        "deposit_interest_application_frequency": "quarterly",
        "interest_application_hour": "0",
        "interest_application_minute": "1",
        "interest_application_second": "0",
    }
    instance_params = {
        **default_instance_params,
        "interest_application_day": "28",
    }
    ```
