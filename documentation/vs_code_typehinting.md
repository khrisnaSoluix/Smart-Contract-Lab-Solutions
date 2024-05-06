_© Thought Machine Group Limited 2022_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Type-hinting in Visual Studio Code (Contracts API 3.x)

## General information

We can leverage the `types_extension` and `features...common_imports/supervisor_imports` to provide type information for smart contracts. Note that not all of the types are fully represented in the Inception library, this is being regularly updated by Inception team, but are not always up to date.

For this type-hinting to work outside of the `inception` repository, please follow the steps below. For type hinting in Inception smart contracts, simply follow step 4.

## Implementation

1. Install Pylance: <https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance>
2. Save the Inception Product Library repo to your local device. For example, your directory tree might look like this:

   ```plaintext
   local_repositories/
   ├─ inception/
   │  ├─ inception_sdk/.../
   │  ├─ library/.../
   ├─ other_repos/
   ```

3. Add the following code snippet to your VS Code's `settings.json`, where the path is replaced by the absolute path to the inception folder on your device:

   ```json
   "python.analysis.extraPaths": ["/Users/$YOUR_USER/local_repositories/inception"],
   ```

4. At the top of the contract you are developing, paste the following code:
   * for Smart Contracts: `from library.features.v3.common.common_imports import *`
   * for Supervisor Contracts: `from library.features.v3.common.supervisor_imports import *`

Note that this might raise some linting errors on your files - the Inception library's `setup.cfg` config file has some useful configurations which could be extended to your other repositories.

Also, please remember to remove this line before uploading a product to Vault, it is not valid for smart contracts and will fail the upload.

# Type-hinting in Visual Studio Code (Contracts API 4.x)

As Contracts API 4.x contracts are syntactically valid Python files the workarounds described above are no longer needed. We rely on `mypy` for type checking, and encourage users to follow their preferred IDE configurations. See `documentation/style_guides/python.md` for more information.
