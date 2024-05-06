# Git Source Finder

## Overview

With the introduction of product composition (see `documentation/product_composition.md` - `Versioning` section) there is a requirement to retrieve source code from the Git repo by its file hash. This tool will take the file hash provided and compare it with every source file from every commit within the current repo. It does this by iterating over each commit, building the source file from each file change within the commit, calculating the checksum of the file and comparing it with the one passed in.

## Usage

Pass the file hash (and optionally git commit hash) of any file in the repo to the tool to print the source file that corresponds to that hash:

```bash
plz git-source --file_hash ff65c769b032333be8c0fb9fdb1be83b --git_commit_hash 0697b8f2e1f3a8149fd836ae11cb721e1190dc2d
```

or

```bash
python3.10 inception_sdk/tools/git_source_finder/main.py -h ff65c769b032333be8c0fb9fdb1be83b -g 0697b8f2e1f3a8149fd836ae11cb721e1190dc2d
```

This will result in an output such as

```bash
python3.10 inception_sdk/tools/git_source_finder/main.py --file_hash ff65c769b032333be8c0fb9fdb1be83b
2023-02-16 15:57:16.831 - INFO: Looking for repo at or above `.`
2023-02-16 15:57:16.833 - INFO: Using repo at `/home/my_user/git/inception`
2023-02-16 15:57:16.833 - INFO: Loading cache from `.gsfcache`
2023-02-16 15:57:16.853 - INFO: Analyzing git repository in /home/my_user/git/inception
2023-02-16 15:57:16.863 - INFO: Commit #d2521c5eb4e745c10326ba8501dd2c1f12282423 in 2022-05-04 10:52:26+00:00 from <redacted>
2023-02-16 15:57:16.872 - INFO: File hash (md5): ff65c769b032333be8c0fb9fdb1be83b
2023-02-16 15:57:16.872 - INFO: Git commit hash: d2521c5eb4e745c10326ba8501dd2c1f12282423
```

As mentioned above, this is most useful when used in conjunction with Feature Level Composition for retrieval of historic source files that make up a rendered contract.

## Cache file

To decrease the lookup time, the tool will write a cache file to a directory. This contains a list of all previously seen commit hashes and a mapping of file checksums against their commit hashes. If a cache file exists and the checksum cannot be found in the cache, the cache is updated with the latest set of commits from the repo. This is increasingly useful as the number of commits in the repository increases.

Writing to the cache file can be disabled with the argument `--save_cache_file=False`.
The cache path can be provided with the argument `--cache_filepath`
