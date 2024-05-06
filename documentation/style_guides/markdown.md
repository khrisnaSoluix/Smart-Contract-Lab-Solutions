_© Thought Machine Group Limited 2023_

_All Rights Reserved. Confidential - Limited Distribution to Authorized Persons Only, Pursuant to the Terms of the Agreement between You and Thought Machine Group Limited granting you a licence for the software to which this documentation relates. This software is protected as an unpublished work and constitutes a trade secret of Thought Machine Group Limited, 5 New Street Square, London EC4A 3TW._

# Markdown

## Linting / Formatting

We use `markdownlint` in the pre-commit hook to consistently and effortlessly lint and format our markdown files.

### Why

Formatting can be a divisive and remarkably time-consuming activity. These tools remove the subjectivity and effort, and guarantee a high level of consistency.

### How

The `markdownlint` will run automatically during the pre-commit hook on any affected markdown files. It will fix any simple fixes and report any errors which require manual resolution. The extensions `DavidAnson.vscode-markdownlint` and `darkriszty.markdown-table-prettify` are included in the recommended extensions pack which will help with ensuring that markdown errors are raised and fixed before commit time (if configured in such a way).

Configuration for the `markdownlint` tool is set in `.markdownlint.json`
