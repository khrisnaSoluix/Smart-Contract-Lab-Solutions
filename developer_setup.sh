#!/usr/bin/env bash
python3.10 -m pip install -r requirements.txt
pre-commit install

pushd inception_sdk/vault/contracts/stubs
python3.10 setup.py bdist_wheel
WHEEL=`find . -type f -iname "contracts_api*.whl"`
pip install $WHEEL --force-reinstall
rm -rf build/
rm -rf dist/
rm -rf contracts_api_stubs.egg-info
popd

pushd inception_sdk/vault/contracts/extensions
python3.10 setup.py bdist_wheel
WHEEL=`find . -type f -iname "contracts_api*.whl"`
pip install $WHEEL --force-reinstall
rm -rf build/
rm -rf dist/
rm -rf contracts_api_extensions.egg-info
popd


git config alias.clean-branches "!git branch -vv | grep ': gone]' | grep -v '\\*' | awk '{ print $1; }' | cut -d ' ' -f3 | xargs -r git branch -d"
git config alias.force-clean-branches "!git branch -vv | grep ': gone]' | grep -v '\\*' | awk '{ print $1; }' | cut -d ' ' -f3 | xargs -r git branch -D"
git config alias.dead-branches "!git branch -vv | grep ': gone]' | grep -v '\\*' | awk '{ print $1; }' | cut -d ' ' -f3 "
